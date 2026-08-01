import json
import pathlib
import re
import time

from dotenv import load_dotenv
from langchain_core.globals import set_verbose, set_debug
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq.chat_models import ChatGroq
from langgraph.constants import END
from langgraph.graph import StateGraph

from agent.prompts import planner_prompt, architect_prompt, coder_system_prompt, coder_user_prompt
from agent.states import Plan, TaskPlan, CoderState, ImplementationTask, File
from agent.tools import set_file_write_callback

_ = load_dotenv()

set_debug(False)
set_verbose(False)

PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"

# Powerful model for code generation and planning without tool calling
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    max_retries=5,
    temperature=0
)


def _emit(state: dict, event_type: str, data: dict = None):
    cb = state.get("_event_callback")
    if cb:
        try:
            cb(event_type, data or {})
        except Exception:
            pass


def _read_file(filepath: str) -> str:
    p = (PROJECT_ROOT / filepath).resolve()
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def _write_file(filepath: str, content: str):
    p = (PROJECT_ROOT / filepath).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    from agent.tools import _file_write_callback
    if _file_write_callback:
        try:
            _file_write_callback(filepath, content)
        except Exception:
            pass


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a plain-text LLM response."""
    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try stripping markdown fences
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in LLM response:\n{text[:500]}")


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences from a code response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # remove closing fence
        text = "\n".join(lines).strip()
    return text


# ---------------------------------------------------------------------------
# Planner Agent
# ---------------------------------------------------------------------------
PLANNER_JSON_PROMPT = """
Return ONLY a valid JSON object (no explanation, no markdown) with this exact schema:
{
  "name": "AppName",
  "description": "One-line description",
  "techstack": "HTML, CSS, JavaScript",
  "features": ["feature1", "feature2"],
  "files": [
    {"path": "index.html", "purpose": "Main HTML file"},
    {"path": "style.css", "purpose": "Stylesheet"},
    {"path": "script.js", "purpose": "JavaScript logic"}
  ]
}

RULES:
- Only plain HTML/CSS/vanilla JS projects. No frameworks, no npm, no build tools.
- Keep files to 2-4 max: typically index.html, style.css, script.js.
- CRITICAL: The HTML file MUST include `<link rel="stylesheet" href="style.css">` and `<script src="script.js"></script>` (or the exact filenames generated).
"""


def planner_agent(state: dict) -> dict:
    _emit(state, "planner_start")
    user_prompt = state["user_prompt"]

    messages = [
        SystemMessage(content=PLANNER_PROMPT_SYS),
        HumanMessage(content=f"User request: {user_prompt}\n\n{PLANNER_JSON_PROMPT}"),
    ]

    for attempt in range(3):
        try:
            resp = llm.invoke(messages)
            data = _extract_json(resp.content)
            plan = Plan(
                name=data.get("name", "App"),
                description=data.get("description", ""),
                techstack=data.get("techstack", "HTML, CSS, JS"),
                features=data.get("features", []),
                files=[File(path=f["path"], purpose=f["purpose"]) for f in data.get("files", [])],
            )
            _emit(state, "planner_done", {
                "plan": {
                    "name": plan.name,
                    "description": plan.description,
                    "techstack": plan.techstack,
                    "features": plan.features,
                    "files": [{"path": f.path, "purpose": f.purpose} for f in plan.files],
                }
            })
            return {**state, "plan": plan}
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise e


PLANNER_PROMPT_SYS = """You are a project planner. Given a user request, design a simple browser-runnable project.
Output only a JSON object. No text before or after it."""


# ---------------------------------------------------------------------------
# Architect Agent
# ---------------------------------------------------------------------------
ARCHITECT_JSON_PROMPT = """
Return ONLY a valid JSON object (no explanation, no markdown) with this exact schema:
{
  "implementation_steps": [
    {
      "filepath": "index.html",
      "task_description": "Detailed description of exactly what to implement in this file"
    }
  ]
}

RULES:
- One entry per file. Order: HTML → CSS → JS.
- Task descriptions must be specific: list every ID, class name, function, and event listener needed.
- The JS file must reference only IDs and classes that are defined in the HTML file.
- CRITICAL: Explicitly specify that the HTML file task MUST include loading the CSS and JS files (`<link>` and `<script>`).
"""


def architect_agent(state: dict) -> dict:
    _emit(state, "architect_start")
    plan: Plan = state["plan"]

    plan_summary = (
        f"Project: {plan.name}\n"
        f"Description: {plan.description}\n"
        f"Tech: {plan.techstack}\n"
        f"Features: {', '.join(plan.features)}\n"
        f"Files: {', '.join(f.path for f in plan.files)}"
    )

    messages = [
        SystemMessage(content="You are a software architect. Given a project plan, create detailed implementation tasks per file. Output only a JSON object."),
        HumanMessage(content=f"{plan_summary}\n\n{ARCHITECT_JSON_PROMPT}"),
    ]

    for attempt in range(3):
        try:
            resp = llm.invoke(messages)
            data = _extract_json(resp.content)
            steps = [
                ImplementationTask(
                    filepath=s["filepath"],
                    task_description=s["task_description"]
                )
                for s in data.get("implementation_steps", [])
            ]
            task_plan = TaskPlan(implementation_steps=steps)
            task_plan.plan = plan

            _emit(state, "architect_done", {
                "tasks": [{"filepath": s.filepath, "task_description": s.task_description} for s in steps]
            })
            return {**state, "task_plan": task_plan}
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise e


# ---------------------------------------------------------------------------
# Coder Agent
# ---------------------------------------------------------------------------
def coder_agent(state: dict) -> dict:
    coder_state: CoderState = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps
    if coder_state.current_step_idx >= len(steps):
        return {**state, "coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]
    step_num = coder_state.current_step_idx + 1
    total = len(steps)

    _emit(state, "coder_start", {
        "step": step_num,
        "total": total,
        "filepath": current_task.filepath,
        "task": current_task.task_description[:200],
    })

    existing_content = _read_file(current_task.filepath)

    # Build cross-file context so JS knows what IDs/classes exist in HTML
    all_files_context = ""
    if PROJECT_ROOT.exists():
        for f in sorted(PROJECT_ROOT.rglob("*")):
            if f.is_file() and f.name != current_task.filepath.split("/")[-1]:
                rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
                try:
                    snippet = f.read_text(encoding="utf-8")
                    if len(snippet) > 3000:
                        snippet = snippet[:3000] + "\n... (truncated)"
                    all_files_context += f"\n--- {rel} ---\n{snippet}\n"
                except Exception:
                    pass

    system_msg = SystemMessage(content=coder_system_prompt())
    user_msg = HumanMessage(content=coder_user_prompt(
        task_description=current_task.task_description,
        filepath=current_task.filepath,
        existing_content=existing_content,
        all_files_context=all_files_context,
    ))

    # Plain text call — zero tool calling, zero JSON serialization of code
    for attempt in range(3):
        try:
            response = llm.invoke([system_msg, user_msg])
            code = _strip_code_fences(response.content)
            if code:
                _write_file(current_task.filepath, code)
                break
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise e

    _emit(state, "coder_step_done", {"step": step_num, "total": total})
    coder_state.current_step_idx += 1
    return {**state, "coder_state": coder_state, "status": "CONTINUE"}


# ---------------------------------------------------------------------------
# Editor Architect Agent
# ---------------------------------------------------------------------------
EDITOR_ARCHITECT_JSON_PROMPT = """
Return ONLY a valid JSON object (no explanation, no markdown) with this exact schema:
{
  "implementation_steps": [
    {
      "filepath": "index.html",
      "task_description": "Detailed description of exactly what to change, add, or remove in this file"
    }
  ]
}

RULES:
- ONLY include files that actually need to be modified based on the user's request. Do not include files that should remain unchanged.
- If a new file needs to be created, include it in the list.
- Task descriptions must be extremely specific about what to change.
"""

def editor_architect_agent(state: dict) -> dict:
    _emit(state, "planner_start") # Reusing planner_start for UI simplicity
    _emit(state, "planner_done", {
        "plan": {
            "name": "Project Update",
            "description": "Analyzing request and existing files...",
            "techstack": "HTML, CSS, JS",
            "features": [],
            "files": []
        }
    })
    
    _emit(state, "architect_start")
    user_prompt = state["user_prompt"]

    # Build context of existing files
    all_files_context = ""
    if PROJECT_ROOT.exists():
        for f in sorted(PROJECT_ROOT.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")
                try:
                    snippet = f.read_text(encoding="utf-8")
                    all_files_context += f"\n--- {rel} ---\n{snippet}\n"
                except Exception:
                    pass

    messages = [
        SystemMessage(content="You are an Editor Architect. The user wants to modify an existing project. Analyze their request and the existing codebase, then output a JSON list of files that need to be modified or created."),
        HumanMessage(content=f"User request: {user_prompt}\n\nExisting Codebase:\n{all_files_context}\n\n{EDITOR_ARCHITECT_JSON_PROMPT}"),
    ]

    for attempt in range(3):
        try:
            resp = llm.invoke(messages)
            data = _extract_json(resp.content)
            steps = [
                ImplementationTask(
                    filepath=s["filepath"],
                    task_description=s["task_description"]
                )
                for s in data.get("implementation_steps", [])
            ]
            
            # If the LLM returned nothing, fallback
            if not steps:
                steps = [ImplementationTask(filepath="index.html", task_description="Review and apply user request")]

            task_plan = TaskPlan(implementation_steps=steps)
            
            # Clear coder_state to ensure we start from step 0
            state.pop("coder_state", None)
            
            _emit(state, "architect_done", {
                "tasks": [{"filepath": s.filepath, "task_description": s.task_description} for s in steps]
            })
            return {**state, "task_plan": task_plan}
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            raise e

# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
graph = StateGraph(dict)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("editor_architect", editor_architect_agent)
graph.add_node("coder", coder_agent)
graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")
graph.add_edge("editor_architect", "coder")

graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"}
)

graph.set_conditional_entry_point(
    lambda s: "editor_architect" if s.get("is_update") else "planner",
    {"editor_architect": "editor_architect", "planner": "planner"}
)
agent = graph.compile()

if __name__ == "__main__":
    set_debug(True)
    set_verbose(True)
    result = agent.invoke({"user_prompt": "Build a todo app in html css and js"},
                          {"recursion_limit": 100})
    print("Final State:", result)
