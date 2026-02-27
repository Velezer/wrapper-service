from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
from app import DEFAULT_CHATGPT_URL, MAX_TIMEOUT_MS, AppState, app_state_from_env, create_app


def test_post_ask_success_path_returns_answer(monkeypatch):
    app = create_app(AppState(timeout_ms=5000, chatgpt_url=DEFAULT_CHATGPT_URL))

    def fake_ask(_prompt: str, _state: AppState) -> str:
        return "hello"

    monkeypatch.setattr(app_module, "ask_via_browser", fake_ask)

    response = TestClient(app).post("/ask", json={"prompt": "hello"})

    assert response.status_code == 200
    assert response.json() == {"answer": "hello"}


def test_404_fallback_path_returns_not_found():
    app = create_app(AppState(timeout_ms=5000, chatgpt_url=DEFAULT_CHATGPT_URL))

    response = TestClient(app).get("/")

    assert response.status_code == 404
    assert response.json() == {"error": "Not found"}


def test_empty_prompt_returns_400():
    app = create_app(AppState(timeout_ms=5000, chatgpt_url=DEFAULT_CHATGPT_URL))

    response = TestClient(app).post("/ask", json={"prompt": "   "})

    assert response.status_code == 400
    assert response.json() == {"error": 'Field "prompt" must be a non-empty string'}


def test_browser_error_is_returned_as_502(monkeypatch):
    app = create_app(AppState(timeout_ms=5000, chatgpt_url=DEFAULT_CHATGPT_URL))

    def fake_ask(_prompt: str, _state: AppState) -> str:
        raise RuntimeError("Browser automation failed: boom")

    monkeypatch.setattr(app_module, "ask_via_browser", fake_ask)

    response = TestClient(app).post("/ask", json={"prompt": "hello"})

    assert response.status_code == 502
    assert response.json() == {"error": "Browser automation failed: boom"}


def test_app_state_from_env_caps_timeout_at_3_minutes(monkeypatch):
    monkeypatch.setenv("GPT_TIMEOUT_MS", "999999")
    monkeypatch.setenv("CHATGPT_URL", "https://example.com")

    state = app_state_from_env()

    assert state.timeout_ms == MAX_TIMEOUT_MS
    assert state.chatgpt_url == "https://example.com"


def test_app_state_from_env_uses_default_url(monkeypatch):
    monkeypatch.delenv("CHATGPT_URL", raising=False)

    state = app_state_from_env()

    assert state.chatgpt_url == DEFAULT_CHATGPT_URL


def test_playwright_unavailable_error_is_helpful(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.sync_api":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError) as exc_info:
        app_module.ask_via_browser("hello", AppState(timeout_ms=2000, chatgpt_url=DEFAULT_CHATGPT_URL))

    message = str(exc_info.value)
    assert "playwright is unavailable" in message
    assert "pip install playwright" in message


def test_dockerfile_installs_chromium_for_playwright():
    dockerfile_text = Path("Dockerfile").read_text(encoding="utf-8")

    assert "python -m pip install --no-cache-dir playwright" in dockerfile_text
    assert "python -m playwright install chromium" in dockerfile_text
    assert "python -m playwright install --with-deps chromium" not in dockerfile_text


def test_composer_selectors_include_prompt_textarea_variants():
    assert "textarea#prompt-textarea" in app_module.COMPOSER_SELECTOR_CANDIDATES
    assert 'div#prompt-textarea[contenteditable="true"]' in app_module.COMPOSER_SELECTOR_CANDIDATES
