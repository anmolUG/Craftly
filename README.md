# Craftly: Autonomous AI Software Engineer

Craftly is an advanced, multi-agent AI coding assistant built on top of LangGraph, FastAPI, and vanilla Web technologies. It functions as an autonomous development team that can process natural language requests, architect a complete web application, generate the code, and iteratively refine it based on human feedback.

## Architecture & Core Features

Craftly employs a state-of-the-art Multi-Agent Architecture powered by LangGraph, coordinating different specialized agents to handle distinct phases of software development:

### 1. Multi-Agent Generation Pipeline
- **Planner Agent**: Analyzes the initial user prompt, determines the optimal tech stack (HTML, CSS, JavaScript), and outlines the project features and required files.
- **Architect Agent**: Translates the high-level plan into granular, file-by-file implementation steps and technical specifications.
- **Coder Agent**: Receives the exact specifications from the Architect and writes the source code to disk.

### 2. Human-in-the-Loop Iterative Editing
Unlike one-shot code generators, Craftly supports continuous iteration:
- **Editor Architect**: When an existing project is loaded, follow-up prompts are routed to the Editor Architect. This agent analyzes the user's requested changes alongside the entire existing codebase.
- **Surgical Updates**: The Editor Architect instructs the Coder to selectively overwrite only the files that require modification, preserving all other existing code and preventing regression.

### 3. Real-Time Streaming & WebSockets
- **FastAPI WebSockets**: The backend streams agent reasoning, state transitions, and file generation events in real-time to the frontend.
- **Collapsible Activity Feed**: Users can track the exact decision-making process of the Planner and Architect agents via an interactive UI, expanding the feed to see the granular tasks planned before execution.

### 4. Resilient Plain-Text Extraction
- **Bypassing JSON Limitations**: Generating complex JavaScript and CSS often breaks native LLM JSON parsers. Craftly utilizes a custom plain-text extraction pipeline that allows the underlying models (like Llama 3.1 and GPT-120b via Groq) to output code naturally in Markdown blocks, ensuring 100 percent syntactic correctness without tool-calling errors.

### 5. Live Dual-Pane IDE
- **Instant Preview**: Generated applications are immediately served into a sandboxed iframe, providing an instant visual preview of the HTML/CSS/JS output.
- **Code Inspector**: Users can toggle to the Code tab to inspect the raw generated source files natively in the browser.

## Getting Started

### Prerequisites
- Python 3.10+
- uv package manager (recommended for fast installation)
- A Groq API Key

### Installation

1. Clone the repository and navigate into the directory.
2. Create and activate a virtual environment:
   ```bash
   uv venv
   source .venv/bin/activate
   ```
   (On Windows use: `.venv\Scripts\activate`)
3. Install the dependencies:
   ```bash
   uv pip install -r pyproject.toml
   ```
4. Set up your environment variables by renaming `.sample_env` to `.env` and adding your Groq API key:
   ```env
   GROQ_API_KEY=your_api_key_here
   ```

### Running Craftly

Start the FastAPI server:
```bash
python server.py
```
Open your browser and navigate to `http://localhost:8000`.

## Example Prompts
- "Build a fully functional Tic-Tac-Toe game with a dark mode toggle and win animations."
- "Create a personal portfolio landing page with a hero section, an about me section, and a contact form."
- Follow-up (Edit): "Change the primary color theme to emerald green and make the buttons rounded."

## License
Copyright (c) Anmol B Rao. All rights reserved.