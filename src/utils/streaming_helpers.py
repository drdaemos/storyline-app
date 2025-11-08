"""Utilities for Server-Sent Events (SSE) streaming in FastAPI."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from typing import Any

from pydantic import BaseModel


async def create_sse_stream(
    task_fn: Callable[[], tuple[Any, ...]],
    chunk_queue: asyncio.Queue[str | None],
    event_queue: asyncio.Queue[dict[str, Any] | None] | None = None,
) -> tuple[Any, ...]:
    """
    Run a task function in an executor and manage completion signals.

    Args:
        task_fn: The function to run in executor. Should return a tuple of results.
        chunk_queue: Queue for text chunks (will receive None when complete)
        event_queue: Optional queue for event dicts (will receive None when complete)

    Returns:
        The result tuple from task_fn
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, task_fn)
        return result
    finally:
        # Signal completion
        await chunk_queue.put(None)
        if event_queue is not None:
            await event_queue.put(None)


async def generate_sse_events(
    chunk_queue: asyncio.Queue[str | None],
    event_queue: asyncio.Queue[dict[str, Any] | None] | None,
    chunk_event_type: str = "chunk",
    chunk_key: str = "content",
) -> AsyncGenerator[str, None]:
    """
    Generate Server-Sent Events from chunk and event queues.

    Args:
        chunk_queue: Queue containing text chunks and None completion signal
        event_queue: Optional queue containing event dicts and None completion signal
        chunk_event_type: The event type to use for chunk events (default: "chunk")
        chunk_key: The key to use for chunk content in event JSON (default: "content")

    Yields:
        SSE formatted strings (data: {...})
    """
    chunk_done = False
    event_done = event_queue is None  # If no event queue, mark as done

    while not (chunk_done and event_done):
        # Create tasks for queues that aren't done
        chunk_task = asyncio.create_task(chunk_queue.get()) if not chunk_done else None
        event_task = (
            asyncio.create_task(event_queue.get()) if event_queue and not event_done else None
        )

        tasks = [task for task in [chunk_task, event_task] if task is not None]
        if not tasks:
            break

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel pending tasks to avoid resource leaks
        for task in pending:
            task.cancel()

        for task in done:
            if task == chunk_task and chunk_task is not None:
                chunk = await chunk_task
                if chunk is None:  # Completion signal
                    chunk_done = True
                else:
                    import json

                    chunk_data = {"type": chunk_event_type, chunk_key: chunk}
                    yield f"data: {json.dumps(chunk_data)}\n\n"
            elif task == event_task and event_task is not None:
                event = await event_task
                if event is None:  # Completion signal
                    event_done = True
                else:
                    import json

                    yield f"data: {json.dumps(event)}\n\n"


def create_sse_event(event_model: BaseModel) -> str:
    """Format a Pydantic model as an SSE event."""
    return f"data: {event_model.model_dump_json()}\n\n"
