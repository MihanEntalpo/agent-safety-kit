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
    def __init__(self) -> None:
        self.console = Console()
        self._progress = Progress(
            SpinnerColumn(),
            BarColumn(bar_width=24),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TextColumn("{task.description}"),
            console=self.console,
            transient=False,
        )

    def __enter__(self) -> "ProgressManager":
        self._progress.start()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._progress.stop()

    def add_task(self, description: str, total: int) -> TaskID:
        return self._progress.add_task(description, total=total)

    def update(self, task_id: TaskID, *, description: Optional[str] = None, completed: Optional[int] = None) -> None:
        self._progress.update(task_id, description=description, completed=completed)

    def advance(self, task_id: TaskID, amount: int = 1) -> None:
        self._progress.advance(task_id, amount)

    def print(self, message: str) -> None:
        self._progress.console.print(message)

    def remove_task(self, task_id: TaskID) -> None:
        self._progress.remove_task(task_id)

    @contextmanager
    def suspend(self) -> Iterable[None]:
        self._progress.stop()
        try:
            yield
        finally:
            self._progress.start()
