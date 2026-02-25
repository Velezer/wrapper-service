# syntax=docker/dockerfile:1

FROM rust:1.89-bookworm AS builder
WORKDIR /app

COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests

RUN cargo test --test ask_e2e
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir playwright \
    && python3 -m playwright install chromium \
    && python3 -c "from playwright.sync_api import sync_playwright"

COPY --from=builder /app/target/release/wrapper-service /usr/local/bin/wrapper-service
COPY --from=builder /app/scripts ./scripts

ENV PORT=3000
ENV GPT_TIMEOUT_MS=20000
ENV CHATGPT_BROWSER_CMD="python3 scripts/chatgpt_browser_bridge.py"

EXPOSE 3000

CMD ["wrapper-service"]
