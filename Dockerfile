FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        fonts-liberation \
        fonts-unifont \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libpango-1.0-0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m pip install --no-cache-dir playwright \
    && python -m playwright install chromium

COPY app.py ./
COPY scripts ./scripts
COPY tests ./tests

ENV PORT=3000
ENV GPT_TIMEOUT_MS=20000
ENV CHATGPT_BROWSER_CMD="python3 scripts/chatgpt_browser_bridge.py"

EXPOSE 3000

CMD ["python", "app.py"]
