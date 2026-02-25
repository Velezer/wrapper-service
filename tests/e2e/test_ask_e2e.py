import os
import socket
import subprocess
import time

import httpx


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


def test_post_ask_e2e_returns_answer_without_mocking():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    # No monkeypatching: this command is actually executed by app.py through subprocess.run.
    cmd = "python3 -c \"import os; print('E2E:' + os.environ['CHATGPT_PROMPT'])\""
    env = {
        **os.environ,
        "CHATGPT_BROWSER_CMD": cmd,
        "GPT_TIMEOUT_MS": "3000",
    }

    server = subprocess.Popen(
        ["python3", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_until_ready(base_url)

        response = httpx.post(
            f"{base_url}/ask",
            json={"prompt": "hello from e2e"},
            timeout=5.0,
        )

        assert response.status_code == 200
        assert response.json() == {"answer": "E2E:hello from e2e"}
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
