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

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip bash ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment and install Playwright
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir playwright \
    && /opt/venv/bin/python -m playwright install chromium

# Add venv to PATH
ENV PATH="/opt/venv/bin:$PATH"

# Copy Rust binaries and scripts
COPY --from=builder /app/target/release/wrapper-service /usr/local/bin/wrapper-service
COPY --from=builder /app/scripts ./scripts

ENV PORT=3000
ENV GPT_TIMEOUT_MS=20000
ENV CHATGPT_BROWSER_CMD="python3 scripts/chatgpt_browser_bridge.py"

EXPOSE 3000

CMD ["wrapper-service"]
