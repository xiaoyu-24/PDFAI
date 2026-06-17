from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock


class TaskRunner:
    def __init__(self, execute: Callable[[int], None], max_workers: int = 3):
        self._execute = execute
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[int, Future] = {}
        self._lock = Lock()

    def submit(self, task_id: int) -> Future:
        with self._lock:
            existing = self._futures.get(task_id)
            if existing and not existing.done():
                return existing
            future = self._executor.submit(self._execute, task_id)
            self._futures[task_id] = future
            future.add_done_callback(lambda _: self._forget(task_id))
            return future

    def _forget(self, task_id: int) -> None:
        with self._lock:
            future = self._futures.get(task_id)
            if future and future.done():
                self._futures.pop(task_id, None)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
