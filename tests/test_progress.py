from agsekit_cli.progress import ProgressManager, StatusSpinner


def test_progress_halt_prints_blank_line(monkeypatch):
    printed = []

    class DummyProgress:
        def stop(self):
            printed.append("stopped")

    class DummyConsole:
        def print(self, message=""):
            printed.append(message)

    manager = ProgressManager()
    manager._progress = DummyProgress()
    manager.console = DummyConsole()

    manager.halt()

    assert printed == ["stopped", ""]
    assert manager._progress is None


def test_status_spinner_restarts_after_suspend():
    events = []

    class DummyStatus:
        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

        def update(self, message):
            events.append(("update", message))

    class DummyConsole:
        is_terminal = True

        def status(self, message, spinner):
            events.append(("status", message, spinner))
            return DummyStatus()

    spinner = StatusSpinner(enabled=True, spinner="dots")
    spinner.console = DummyConsole()
    spinner.enabled = True

    spinner.update("Checking mount state")
    with spinner.suspend():
        events.append("inside")

    assert events == [
        ("status", "Checking mount state", "dots"),
        "start",
        "stop",
        "inside",
        ("status", "Checking mount state", "dots"),
        "start",
    ]
