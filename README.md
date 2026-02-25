# wrapper-service (Python)

A FastAPI wrapper service exposing `POST /ask` and forwarding prompts to the browser bridge script.

The browser bridge now self-heals missing Playwright runtime dependencies by attempting to install
the Python package and Chromium browser on first run when they are missing.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Test

```bash
pytest
```
