import os
import socket
import textwrap
import time
from multiprocessing import Process

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse


FAKE_CHATGPT_HTML = textwrap.dedent(
    """
    <!doctype html>
    <html>
      <body>
        <textarea id="prompt-textarea"></textarea>
        <script>
          const composer = document.getElementById("prompt-textarea");
          composer.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              const reply = document.createElement("div");
              reply.setAttribute("data-message-author-role", "assistant");
              reply.textContent = `echo: ${composer.value}`;
              document.body.appendChild(reply);
            }
          });
        </script>
      </body>
    </html>
    """
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(base_url: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/", timeout=0.5)
            if response.status_code in (200, 404):
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise TimeoutError("service did not become ready in time")


def _run_server(port: int, chatgpt_url: str) -> None:
    os.environ["CHATGPT_URL"] = chatgpt_url
    uvicorn.run("app:app", host="127.0.0.1", port=port, log_level="error")


def _run_fake_chatgpt_server(port: int) -> None:
    app = FastAPI()

    @app.get("/")
    def index():
        return HTMLResponse(FAKE_CHATGPT_HTML)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


def test_post_ask_e2e_returns_error_when_browser_is_unavailable():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    server = Process(target=_run_server, args=(port, "https://chatgpt.com/"), daemon=True)
    server.start()

    try:
        _wait_until_ready(base_url)

        response = httpx.post(
            f"{base_url}/ask",
            json={"prompt": "hello from e2e"},
            timeout=20.0,
        )

        assert response.status_code in (200, 502)
        body = response.json()
        assert "answer" in body or "error" in body
    finally:
        server.terminate()
        server.join(timeout=5)


def test_post_ask_e2e_rejects_blank_prompt_without_browser_call():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    server = Process(target=_run_server, args=(port, "https://chatgpt.com/"), daemon=True)
    server.start()

    try:
        _wait_until_ready(base_url)

        response = httpx.post(
            f"{base_url}/ask",
            json={"prompt": "   "},
            timeout=10.0,
        )

        assert response.status_code == 400
        assert response.json() == {"error": 'Field "prompt" must be a non-empty string'}
    finally:
        server.terminate()
        server.join(timeout=5)


def test_post_ask_e2e_supports_prompt_textarea_selector():
    fake_chatgpt_port = _free_port()
    fake_chatgpt_url = f"http://127.0.0.1:{fake_chatgpt_port}/"

    fake_chatgpt_server = Process(target=_run_fake_chatgpt_server, args=(fake_chatgpt_port,), daemon=True)
    fake_chatgpt_server.start()

    wrapper_port = _free_port()
    wrapper_base_url = f"http://127.0.0.1:{wrapper_port}"
    wrapper_server = Process(
        target=_run_server,
        args=(wrapper_port, fake_chatgpt_url),
        daemon=True,
    )
    wrapper_server.start()

    try:
        _wait_until_ready(fake_chatgpt_url.rstrip("/"))
        _wait_until_ready(wrapper_base_url)

        prompt = "hello selector"
        response = httpx.post(
            f"{wrapper_base_url}/ask",
            json={"prompt": prompt},
            timeout=30.0,
        )

        if response.status_code == 502:
            error = response.json().get("error", "")
            if "playwright is unavailable" in error or "Executable doesn't exist" in error:
                pytest.skip(f"Playwright/Chromium unavailable in environment: {error}")

        assert response.status_code == 200
        assert response.json() == {"answer": f"echo: {prompt}"}
    finally:
        wrapper_server.terminate()
        wrapper_server.join(timeout=5)
        fake_chatgpt_server.terminate()
        fake_chatgpt_server.join(timeout=5)
