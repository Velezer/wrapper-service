import subprocess

from fastapi.testclient import TestClient

from app import AppState, create_app, format_browser_command_error


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
