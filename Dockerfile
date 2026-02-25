# syntax=docker/dockerfile:1

FROM rust:1.89-bookworm AS builder
WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests

RUN cargo build --release

FROM debian:bookworm-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir playwright \
    && /opt/venv/bin/playwright install --with-deps chromium

COPY --from=builder /app/target/release/wrapper-service /usr/local/bin/wrapper-service
COPY --from=builder /app/scripts ./scripts

ENV PATH="/opt/venv/bin:${PATH}"
ENV PORT=3000
ENV GPT_TIMEOUT_MS=20000
ENV CHATGPT_BROWSER_CMD="python3 scripts/chatgpt_browser_bridge.py"

EXPOSE 3000

CMD ["wrapper-service"]
