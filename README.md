# wrapper-service (Python)

A FastAPI wrapper service exposing `POST /ask` and forwarding prompts directly through Playwright browser automation.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
python app.py
```

## Configuration

- `GPT_TIMEOUT_MS` controls the maximum time to wait for the assistant response (capped at 180000ms).
- `CHATGPT_URL` controls the target URL for browser navigation (defaults to `https://chatgpt.com/`).

## Test

```bash
pytest
```
