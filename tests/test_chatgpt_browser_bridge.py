import subprocess

from scripts import chatgpt_browser_bridge


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
