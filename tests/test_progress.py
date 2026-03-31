from agsekit_cli.progress import ProgressManager


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
