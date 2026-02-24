#!/usr/bin/env python3
import os
import sys


def main() -> int:
    prompt = os.environ.get("CHATGPT_PROMPT", "Hello from wrapper-service").strip()
    if not prompt:
        prompt = "Hello from wrapper-service"

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        print(f"playwright import failed: {exc}", file=sys.stderr)
        return 3

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)

            composer = page.locator('textarea[placeholder*="Message"], textarea[data-id="root"]')
            composer.first.wait_for(timeout=30000)
            composer.first.fill(prompt)
            composer.first.press("Enter")

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
