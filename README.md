# wrapper-service (Python)

A FastAPI wrapper service exposing `POST /ask` and forwarding prompts to the browser bridge script.

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
