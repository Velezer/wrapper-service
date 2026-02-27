from __future__ import annotations

import os
import time
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

MAX_TIMEOUT_MS = 180_000
DEFAULT_CHATGPT_URL = "https://chatgpt.com/"
COMPOSER_SELECTOR_CANDIDATES = (
    'textarea#prompt-textarea',
    'div#prompt-textarea',
    'div#prompt-textarea[contenteditable="true"]',
    'div#prompt-textarea[contenteditable]',
    'textarea[aria-label*="Message"]',
    'div[contenteditable="true"][aria-label*="Message"]',
    'textarea[placeholder*="Message"]',
    'div[contenteditable="true"][placeholder*="Message"]',
    'textarea[data-id="root"]',
    'div[contenteditable="true"][data-id="root"]',
    'div[contenteditable="plaintext-only"][role="textbox"]',
    'div.ProseMirror[contenteditable="true"]',
    'div[contenteditable="true"][role="textbox"]',
)


@dataclass
class AppState:
    timeout_ms: int
    chatgpt_url: str


class AskRequest(BaseModel):
    prompt: str


def app_state_from_env() -> AppState:
    raw_timeout_ms = int(os.getenv("GPT_TIMEOUT_MS", str(MAX_TIMEOUT_MS)))
    timeout_ms = max(1, min(raw_timeout_ms, MAX_TIMEOUT_MS))
    chatgpt_url = os.getenv("CHATGPT_URL", DEFAULT_CHATGPT_URL)
    return AppState(timeout_ms=timeout_ms, chatgpt_url=chatgpt_url)


def ask_via_browser(prompt: str, state: AppState) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Browser automation failed to start: playwright is unavailable. "
            "Install Playwright with `pip install playwright` and then run "
            "`python3 -m playwright install chromium`."
        ) from exc

    timeout_ms = state.timeout_ms

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.goto(state.chatgpt_url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1500)

            composer = _wait_for_composer(page, timeout_ms=30_000)
            _submit_prompt(composer, prompt)

            response_blocks = page.locator('[data-message-author-role="assistant"]')
            response_blocks.last.wait_for(timeout=timeout_ms)
            text = response_blocks.last.inner_text().strip()

            context.close()
            browser.close()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Browser automation failed: {exc}") from exc

    if not text:
        raise RuntimeError("Browser automation did not return an answer")

    return text


def _wait_for_composer(page, timeout_ms: int):
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_error = None

    while time.monotonic() < deadline:
        remaining_ms = max(200, int((deadline - time.monotonic()) * 1000))
        per_selector_timeout = max(200, min(1_500, remaining_ms // len(COMPOSER_SELECTOR_CANDIDATES)))

        for selector in COMPOSER_SELECTOR_CANDIDATES:
            candidate = page.locator(selector).first
            try:
                candidate.wait_for(state="visible", timeout=per_selector_timeout)
                return candidate
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        page.wait_for_timeout(100)

    raise RuntimeError(
        "Could not find ChatGPT composer using known selectors: "
        f"{', '.join(COMPOSER_SELECTOR_CANDIDATES)}"
    ) from last_error


def _submit_prompt(composer, prompt: str) -> None:
    tag_name = composer.evaluate("(node) => node.tagName")
    if tag_name and str(tag_name).upper() == "TEXTAREA":
        composer.fill(prompt)
    else:
        composer.click()
        composer.type(prompt)
    composer.press("Enter")


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
