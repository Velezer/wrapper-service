import importlib
import subprocess

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from app import MAX_TIMEOUT_MS, AppState, app_state_from_env, ask_via_browser, create_app, format_browser_command_error


def test_post_ask_success_path_returns_answer(monkeypatch):
    app = create_app(AppState(timeout_ms=5000, chatgpt_browser_cmd="echo hello"))

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="hello\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = TestClient(app).post("/ask", json={"prompt": "hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "hello"}


def test_404_fallback_path_returns_not_found():
    app = create_app(AppState(timeout_ms=5000, chatgpt_browser_cmd="echo hello"))

    response = TestClient(app).get("/")

    assert response.status_code == 404
    assert response.json() == {"error": "Not found"}


def test_empty_prompt_returns_400():
    app = create_app(AppState(timeout_ms=5000, chatgpt_browser_cmd="echo hello"))

    response = TestClient(app).post("/ask", json={"prompt": "   "})

    assert response.status_code == 400
    assert response.json() == {"error": 'Field "prompt" must be a non-empty string'}


def test_browser_error_is_returned_as_502(monkeypatch):
    app = create_app(AppState(timeout_ms=5000, chatgpt_browser_cmd="echo hello"))

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = TestClient(app).post("/ask", json={"prompt": "hello"})

    assert response.status_code == 502
    assert response.json() == {"error": "Browser automation command failed: boom"}


def test_playwright_import_error_includes_install_hint():
    err = format_browser_command_error(
        "playwright import failed: No module named 'playwright'",
        "3",
    )

    assert "pip install playwright" in err
    assert "python3 -m playwright install chromium" in err


def test_app_state_from_env_caps_timeout_at_3_minutes(monkeypatch):
    monkeypatch.setenv("GPT_TIMEOUT_MS", "999999")
    monkeypatch.setenv("CHATGPT_BROWSER_CMD", "echo hello")

    state = app_state_from_env()

    assert state.timeout_ms == MAX_TIMEOUT_MS


def test_timeout_error_includes_debug_details(monkeypatch):
    state = AppState(timeout_ms=2000, chatgpt_browser_cmd="python3 scripts/chatgpt_browser_bridge.py")

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="bridge", timeout=2.0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        ask_via_browser("hello", state)

    msg = str(exc_info.value)
    assert "timeout after 2.0s" in msg
    assert "max 180.0s" in msg
    assert "CHATGPT_PROMPT" in msg
    assert "stderr logs" in msg


def test_playwright_import_succeeds():
    pytest.importorskip("playwright.sync_api")
    module = importlib.import_module("playwright.sync_api")
    assert module is not None


def test_dockerfile_installs_chromium_for_playwright():
    dockerfile_text = Path("Dockerfile").read_text(encoding="utf-8")

    assert "python -m pip install --no-cache-dir playwright" in dockerfile_text
    assert "python -m playwright install chromium" in dockerfile_text
    assert "python -m playwright install --with-deps chromium" not in dockerfile_text
