# wrapper-service (Python)

FastAPI service exposing `POST /ask` and forwarding prompts via real Playwright browser automation.

## How to run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

Service starts on `http://127.0.0.1:3000`.

## How to use

Send a JSON payload with a non-empty `prompt`.

```bash
curl -sS http://127.0.0.1:3000/ask \
  -H 'content-type: application/json' \
  -d '{"prompt":"Write a short haiku about testing"}'
```

Success response:

```json
{"answer":"..."}
```

Error response:

```json
{"error":"Browser automation failed: ..."}
```

## Configuration

- `GPT_TIMEOUT_MS`: max time waiting for assistant output (capped at 180000 ms).
- `CHATGPT_URL`: target URL for automation (default `https://chatgpt.com/`).

Composer detection uses multiple selectors and supports common ChatGPT variants (`Message` / `Ask anything`, `textarea`, and `contenteditable` textbox patterns).

## Troubleshooting

- If Playwright is missing: `pip install playwright`
- If Chromium is missing: `python -m playwright install chromium`
- If `/ask` returns a composer-not-found error, make sure your target page is fully loaded and logged in (if required), and that `CHATGPT_URL` points to the exact chat page you expect.

## Tests

```bash
pytest
```

The e2e tests run against a real Uvicorn server process and fake HTML chat surfaces, without mocking subprocess browser execution.
