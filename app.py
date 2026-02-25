from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel


@dataclass
class AppState:
    timeout_ms: int
    chatgpt_browser_cmd: str


class AskRequest(BaseModel):
    prompt: str


def default_chatgpt_browser_cmd() -> str:
    if Path("/opt/venv/bin/python").exists():
        return "/opt/venv/bin/python scripts/chatgpt_browser_bridge.py"
    return "python3 scripts/chatgpt_browser_bridge.py"


def app_state_from_env() -> AppState:
    timeout_ms = int(os.getenv("GPT_TIMEOUT_MS", "20000"))
    cmd = os.getenv("CHATGPT_BROWSER_CMD", default_chatgpt_browser_cmd())
    return AppState(timeout_ms=timeout_ms, chatgpt_browser_cmd=cmd)


def format_browser_command_error(stderr: str, status: str) -> str:
    install_hint = "Install Playwright with `pip install playwright` and then run `python3 -m playwright install chromium`."

    if not stderr:
        return f"Browser automation command failed with status {status}"

    if "playwright import failed" in stderr:
        clean_stderr = stderr.rstrip(".")
        return f"Browser automation command failed: {clean_stderr}. {install_hint}"

    return f"Browser automation command failed: {stderr}"


def ask_via_browser(prompt: str, state: AppState) -> str:
    try:
        output = subprocess.run(
            ["bash", "-lc", state.chatgpt_browser_cmd],
            env={**os.environ, "CHATGPT_PROMPT": prompt},
            capture_output=True,
            text=True,
            timeout=state.timeout_ms / 1000,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ChatGPT browser automation timeout") from exc
    except OSError as exc:
        raise RuntimeError(f"Failed to start browser automation command: {exc}") from exc

    if output.returncode != 0:
        raise RuntimeError(format_browser_command_error(output.stderr.strip(), str(output.returncode)))

    answer = output.stdout.strip()
    if not answer:
        raise RuntimeError("Browser automation did not return an answer")

    return answer


def create_app(state: AppState | None = None) -> FastAPI:
    app = FastAPI()
    app.state.wrapper_state = state or app_state_from_env()

    @app.post("/ask")
    def ask(payload: AskRequest):
        prompt = payload.prompt.strip()
        if not prompt:
            return JSONResponse(
                status_code=400,
                content={"error": 'Field "prompt" must be a non-empty string'},
            )

        try:
            answer = ask_via_browser(prompt, app.state.wrapper_state)
            return JSONResponse(status_code=200, content={"answer": answer})
        except RuntimeError as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})

    @app.exception_handler(404)
    def not_found(_, __):
        return JSONResponse(status_code=404, content={"error": "Not found"})

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
