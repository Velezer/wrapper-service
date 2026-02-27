import os
import socket
import time
from multiprocessing import Process

import httpx
import uvicorn


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_ready(base_url: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/", timeout=0.5)
            if response.status_code == 404:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise TimeoutError("wrapper-service did not become ready in time")


def _run_server(port: int) -> None:
    os.environ["CHATGPT_URL"] = "https://chatgpt.com/"
    uvicorn.run("app:app", host="127.0.0.1", port=port, log_level="error")


def test_post_ask_e2e_returns_error_when_browser_is_unavailable():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    server = Process(target=_run_server, args=(port,), daemon=True)
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

    server = Process(target=_run_server, args=(port,), daemon=True)
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
