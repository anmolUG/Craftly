"""
Coder Buddy — Web Server
FastAPI app with WebSocket for real-time agent event streaming.
Run with: python server.py
"""

import asyncio
import json
import os
import pathlib
import shutil
import traceback
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Ensure UTF-8 output on Windows
os.environ["PYTHONUTF8"] = "1"

app = FastAPI(title="Coder Buddy")

FRONTEND_DIR = pathlib.Path(__file__).parent / "frontend"
PROJECT_ROOT = pathlib.Path(__file__).parent / "generated_project"


# --- Static frontend ---
@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount frontend static files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# --- Preview endpoint: serve generated project files ---
@app.get("/preview/{file_path:path}")
async def serve_preview(file_path: str):
    full_path = (PROJECT_ROOT / file_path).resolve()
    # Security: ensure path is within project root
    if PROJECT_ROOT.resolve() not in full_path.parents and full_path != PROJECT_ROOT.resolve():
        return Response(status_code=403, content="Forbidden")
    if not full_path.exists():
        return Response(status_code=404, content="Not Found")

    # Guess content type
    suffix = full_path.suffix.lower()
    content_types = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }
    content_type = content_types.get(suffix, "text/plain")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return FileResponse(str(full_path), media_type=content_type, headers=headers)


# --- List generated files ---
@app.get("/api/files")
async def list_generated_files():
    if not PROJECT_ROOT.exists():
        return {"files": []}
    files = []
    for f in PROJECT_ROOT.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
            files.append(rel)
    return {"files": sorted(files)}


# --- Read a generated file ---
@app.get("/api/file/{file_path:path}")
async def read_generated_file(file_path: str):
    full_path = (PROJECT_ROOT / file_path).resolve()
    if PROJECT_ROOT.resolve() not in full_path.parents and full_path != PROJECT_ROOT.resolve():
        return Response(status_code=403, content="Forbidden")
    if not full_path.exists():
        return Response(status_code=404, content="Not Found")
    content = full_path.read_text(encoding="utf-8", errors="replace")
    return {"path": file_path, "content": content}


# --- WebSocket: run agent and stream events ---
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            prompt = msg.get("prompt", "")

            if not prompt.strip():
                await ws.send_text(json.dumps({"type": "error", "data": {"message": "Empty prompt"}}))
                continue

            is_update = msg.get("is_update", False)

            # Run agent in background thread
            await run_agent_with_streaming(ws, prompt, is_update)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(json.dumps({"type": "error", "data": {"message": str(e)}}))
        except Exception:
            pass


async def run_agent_with_streaming(ws: WebSocket, prompt: str, is_update: bool = False):
    """Run the LangGraph agent in a thread and stream events via WebSocket."""
    loop = asyncio.get_event_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def event_callback(event_type: str, data: dict):
        """Called from the agent thread. Puts events into the async queue."""
        loop.call_soon_threadsafe(event_queue.put_nowait, (event_type, data))

    def file_write_callback(filepath: str, content: str):
        """Called when the agent writes a file."""
        loop.call_soon_threadsafe(
            event_queue.put_nowait,
            ("file_written", {"filepath": filepath.replace("\\", "/"), "content": content})
        )

    def run_agent():
        """Runs the agent synchronously in a thread."""
        from agent.graph import agent
        from agent.tools import set_file_write_callback, PROJECT_ROOT

        # Clean previous generated project only if it's not an update
        if not is_update:
            if PROJECT_ROOT.exists():
                shutil.rmtree(PROJECT_ROOT, ignore_errors=True)
            PROJECT_ROOT.mkdir(parents=True, exist_ok=True)

        # Set callbacks
        set_file_write_callback(file_write_callback)

        try:
            result = agent.invoke(
                {
                    "user_prompt": prompt, 
                    "is_update": is_update,
                    "_event_callback": event_callback
                },
                {"recursion_limit": 100}
            )
            # Collect final file list
            files = []
            for f in PROJECT_ROOT.rglob("*"):
                if f.is_file():
                    files.append(str(f.relative_to(PROJECT_ROOT)).replace("\\", "/"))
            event_callback("done", {"files": sorted(files)})
        except Exception as e:
            traceback.print_exc()
            event_callback("error", {"message": str(e)})
        finally:
            set_file_write_callback(None)

    # Start agent in background thread
    agent_task = loop.run_in_executor(None, run_agent)

    # Stream events from queue to WebSocket
    try:
        while True:
            try:
                event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                safe_data = json.loads(
                    json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
                )
                await ws.send_text(json.dumps(safe_data, ensure_ascii=False))

                if event_type in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Check if agent thread is still running
                if agent_task.done():
                    # Drain remaining events
                    while not event_queue.empty():
                        event_type, data = event_queue.get_nowait()
                        safe_data = json.loads(
                            json.dumps({"type": event_type, "data": data}, ensure_ascii=False, default=str)
                        )
                        await ws.send_text(json.dumps(safe_data, ensure_ascii=False))
                        if event_type in ("done", "error"):
                            return
                    break
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
