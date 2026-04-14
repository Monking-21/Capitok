import asyncio

from capitok.db import insert_refined_memory
from capitok.queue.interface import QueueAdapter, RefineTask


class InProcessQueueAdapter(QueueAdapter):
    def __init__(self, max_concurrency: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def enqueue_refine_task(self, task: RefineTask) -> None:
        asyncio.create_task(self._handle_task(task))

    async def _handle_task(self, task: RefineTask) -> None:
        async with self._semaphore:
            await asyncio.to_thread(
                insert_refined_memory,
                task.tenant_id,
                task.principal_id,
                task.session_id,
                task.user_id,
                task.text,
                task.embedding_version,
            )
