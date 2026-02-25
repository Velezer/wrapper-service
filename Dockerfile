FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m pip install --no-cache-dir playwright \
    && python -m playwright install --with-deps chromium

COPY app.py ./
COPY scripts ./scripts
COPY tests ./tests

ENV PORT=3000
ENV GPT_TIMEOUT_MS=20000
ENV CHATGPT_BROWSER_CMD="python3 scripts/chatgpt_browser_bridge.py"

EXPOSE 3000

CMD ["python", "app.py"]
