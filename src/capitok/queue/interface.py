from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RefineTask:
    tenant_id: str
    principal_id: str
    session_id: str
    user_id: str
    text: str
    embedding_version: str


class QueueAdapter(Protocol):
    async def enqueue_refine_task(self, task: RefineTask) -> None:
        raise NotImplementedError
