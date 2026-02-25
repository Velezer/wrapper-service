# AGENTS.MD

## Repository notes
- Keep `scripts/chatgpt_browser_bridge.py` resilient when Playwright is missing.
- Runtime should be able to recover from missing Python package or Chromium executable.
- When changing browser-automation behavior, update tests/docs in the same change.
