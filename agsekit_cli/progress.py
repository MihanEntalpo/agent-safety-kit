from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)


class ProgressManager:
    def __init__(self, *, debug: bool = False) -> None:
        self.enabled = not debug
        self.console = Console()
        self._progress = None
        if self.enabled:
            self._progress = Progress(
                SpinnerColumn(),
                BarColumn(bar_width=24),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TextColumn("{task.description}"),
                console=self.console,
                transient=False,
            )

    def __bool__(self) -> bool:
        return self.enabled

    def __enter__(self) -> "ProgressManager":
        if self._progress is not None:
            self._progress.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._progress is not None:
            self._progress.stop()

    def add_task(self, description: str, total: int) -> TaskID:
        if self._progress is None:
            return TaskID(0)
        return self._progress.add_task(description, total=total)

    def update(self, task_id: TaskID, *, description: Optional[str] = None, completed: Optional[int] = None) -> None:
        if self._progress is not None:
            self._progress.update(task_id, description=description, completed=completed)

    def advance(self, task_id: TaskID, amount: int = 1) -> None:
        if self._progress is not None:
            self._progress.advance(task_id, amount)

    def print(self, message: str) -> None:
        if self._progress is not None:
            self._progress.console.print(message)
        else:
            self.console.print(message)

    def remove_task(self, task_id: TaskID) -> None:
        if self._progress is not None:
            self._progress.remove_task(task_id)

    @contextmanager
    def suspend(self) -> Iterable[None]:
        if self._progress is None:
            yield
            return
        self._progress.stop()
        try:
            yield
        finally:
            self._progress.start()
