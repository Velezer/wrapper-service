import subprocess

from scripts import chatgpt_browser_bridge


class _FakeLocator:
    def __init__(self, should_find: bool, fill_raises: bool = False):
        self._should_find = should_find
        self._fill_raises = fill_raises
        self.first = self
        self.actions: list[tuple[str, str | int | None]] = []

    def wait_for(self, timeout: int, state: str | None = None):
        if not self._should_find:
            raise RuntimeError("not found")
        self.actions.append(("wait_for", timeout))

    def click(self):
        self.actions.append(("click", None))

    def type(self, value: str):
        self.actions.append(("type", value))

    def fill(self, value: str):
        self.actions.append(("fill", value))
        if self._fill_raises:
            raise RuntimeError("fill not supported")

    def press(self, value: str):
        self.actions.append(("press", value))


class _FakePage:
    def __init__(self):
        self.locators = {
            'div[contenteditable="true"][data-id="root"]': _FakeLocator(True),
        }

    def locator(self, selector: str):
        return self.locators.get(selector, _FakeLocator(False))

    def wait_for_timeout(self, _timeout: int):
        return None


def test_run_best_effort_logs_warning_when_command_fails(monkeypatch, capsys):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="missing package")

    monkeypatch.setattr(subprocess, "run", fake_run)

    chatgpt_browser_bridge._run_best_effort(["dummy"], "install deps")

    captured = capsys.readouterr()
    assert "warning: install deps failed: missing package" in captured.err


def test_run_checked_raises_when_command_fails(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="broken")

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        chatgpt_browser_bridge._run_checked(["dummy"], "label")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert str(exc) == "label failed: broken"


def test_wait_for_composer_tries_multiple_selectors_and_returns_first_match():
    page = _FakePage()

    composer = chatgpt_browser_bridge._wait_for_composer(page, timeout_ms=4000)

    assert composer is page.locators['div[contenteditable="true"][data-id="root"]']


def test_submit_prompt_prefers_fill_when_available():
    locator = _FakeLocator(True)

    chatgpt_browser_bridge._submit_prompt(locator, "hello")

    assert ("fill", "hello") in locator.actions
    assert ("press", "Enter") in locator.actions


def test_submit_prompt_falls_back_to_typing_when_fill_fails():
    locator = _FakeLocator(True, fill_raises=True)

    chatgpt_browser_bridge._submit_prompt(locator, "hello")

    assert ("click", None) in locator.actions
    assert ("type", "hello") in locator.actions
    assert ("press", "Enter") in locator.actions
