#!/usr/bin/env python3
import os
import subprocess
import sys
import time


COMPOSER_SELECTOR_CANDIDATES = (
    'textarea#prompt-textarea',
    'div#prompt-textarea[contenteditable="true"]',
    'textarea[aria-label*="Message"]',
    'div[contenteditable="true"][aria-label*="Message"]',
    'textarea[placeholder*="Message"]',
    'div[contenteditable="true"][placeholder*="Message"]',
    'textarea[data-id="root"]',
    'div[contenteditable="true"][data-id="root"]',
    'div[contenteditable="true"][role="textbox"]',
)


def _run_checked(cmd: list[str], label: str) -> None:
    """Run a command and raise RuntimeError with stderr when it fails."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"{label} failed: {stderr}")


def _run_best_effort(cmd: list[str], label: str) -> None:
    """Run a command and continue when it fails, printing a warning."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        print(f"warning: {label} failed: {stderr}", file=sys.stderr)


def _ensure_playwright_ready():
    """Return sync_playwright, attempting one-time bootstrap when needed."""
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except Exception:  # noqa: BLE001
        python = sys.executable or "python3"
        _run_checked([python, "-m", "pip", "install", "playwright"], "pip install playwright")
        _run_best_effort([python, "-m", "playwright", "install-deps", "chromium"], "playwright install-deps chromium")
        _run_checked([python, "-m", "playwright", "install", "chromium"], "playwright install chromium")

    from playwright.sync_api import sync_playwright

    return sync_playwright


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


def main() -> int:
    prompt = os.environ.get("CHATGPT_PROMPT", "").strip()
    if not prompt:
        print("CHATGPT_PROMPT is empty", file=sys.stderr)
        return 2

    try:
        sync_playwright = _ensure_playwright_ready()
    except Exception as exc:  # noqa: BLE001
        reason = str(exc).strip() or "unknown import error"
        print(f"playwright import failed: {reason}", file=sys.stderr)
        return 3

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                python = sys.executable or "python3"

                if "Host system is missing dependencies" in msg:
                    _run_best_effort(
                        [python, "-m", "playwright", "install-deps", "chromium"],
                        "playwright install-deps chromium",
                    )
                    browser = p.chromium.launch(headless=True)
                elif "Executable doesn't exist" in msg:
                    _run_checked(
                        [python, "-m", "playwright", "install", "chromium"],
                        "playwright install chromium",
                    )
                    browser = p.chromium.launch(headless=True)
                else:
                    raise
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)

            composer = _wait_for_composer(page, timeout_ms=30000)
            _submit_prompt(composer, prompt)

            response_blocks = page.locator('[data-message-author-role="assistant"]')
            response_blocks.last.wait_for(timeout=120000)
            text = response_blocks.last.inner_text().strip()

            if not text:
                print("assistant response was empty", file=sys.stderr)
                return 4

            print(text)
            context.close()
            browser.close()
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"browser automation failed: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
