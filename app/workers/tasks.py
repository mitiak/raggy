from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BackgroundTask:
    task_name: str
    payload: dict[str, str]


class TaskDispatcher(Protocol):
    async def dispatch(self, task: BackgroundTask) -> None:
        ...
