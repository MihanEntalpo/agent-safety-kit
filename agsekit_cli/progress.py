from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterable, Optional, Union

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

    def update(
        self,
        task_id: TaskID,
        *,
        description: Optional[str] = None,
        completed: Optional[int] = None,
        total: Optional[int] = None,
    ) -> None:
        if self._progress is not None:
            self._progress.update(task_id, description=description, completed=completed, total=total)

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


class SingleTaskProgressProxy:
    def __init__(self, progress: ProgressManager) -> None:
        self._progress = progress
        self._enabled = bool(progress)
        self._task_id = progress.add_task("", total=1) if self._enabled else TaskID(0)
        self._states: Dict[int, Dict[str, Union[int, str]]] = {}
        self._stack: list[int] = []
        self._next_id = 1

    def __bool__(self) -> bool:
        return self._enabled

    def __enter__(self) -> "SingleTaskProgressProxy":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def add_task(self, description: str, total: int) -> int:
        synthetic_id = self._next_id
        self._next_id += 1
        self._states[synthetic_id] = {
            "description": description,
            "completed": 0,
            "total": max(total, 1),
        }
        self._stack.append(synthetic_id)
        self._render()
        return synthetic_id

    def update(
        self,
        task_id: int,
        *,
        description: Optional[str] = None,
        completed: Optional[int] = None,
        total: Optional[int] = None,
    ) -> None:
        state = self._states.get(task_id)
        if state is None:
            return
        if description is not None:
            state["description"] = description
        if completed is not None:
            state["completed"] = completed
        if total is not None:
            state["total"] = max(total, 1)
        self._render()

    def advance(self, task_id: int, amount: int = 1) -> None:
        state = self._states.get(task_id)
        if state is None:
            return
        state["completed"] = int(state["completed"]) + amount
        self._render()

    def remove_task(self, task_id: int) -> None:
        self._states.pop(task_id, None)
        self._stack = [existing for existing in self._stack if existing != task_id]
        self._render()

    def print(self, message: str) -> None:
        self._progress.print(message)

    @contextmanager
    def suspend(self) -> Iterable[None]:
        with self._progress.suspend():
            yield

    def close(self) -> None:
        if self._enabled:
            self._progress.remove_task(self._task_id)

    def _render(self) -> None:
        if not self._enabled:
            return
        if not self._stack:
            self._progress.update(self._task_id, description="", completed=0, total=1)
            return
        active_id = self._stack[-1]
        state = self._states[active_id]
        self._progress.update(
            self._task_id,
            description=str(state["description"]),
            completed=int(state["completed"]),
            total=int(state["total"]),
        )
