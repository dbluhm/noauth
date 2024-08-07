"""Temporal KV Store."""

import asyncio
import heapq
import logging
import time
from typing import Any, Dict, List, Tuple


LOGGER = logging.getLogger(__name__)


class TemporalKVStore:
    """KV Store with TTL expiry."""

    def __init__(self):
        """Initialize the store."""
        self.store: Dict[str, Any] = {}
        self.expiry_heap: List[Tuple[float, str]] = []
        self._lock: asyncio.Lock | None = None
        self._expiry_task: asyncio.Task | None = None
        self._new_expiry_event: asyncio.Event | None = None
        self._ready_event: asyncio.Event | None = None

    async def open(self):
        """Open the store."""
        self._lock = asyncio.Lock()
        self._ready_event = asyncio.Event()
        self._new_expiry_event = asyncio.Event()
        self._expiry_task = asyncio.create_task(self._expiry_loop())
        await self._ready_event.wait()
        return self

    @property
    def lock(self) -> asyncio.Lock:
        """Get lock."""
        assert self._lock is not None, "Store is not open"
        return self._lock

    @property
    def expiry_task(self) -> asyncio.Task:
        """Get expiry task."""
        assert self._expiry_task is not None, "Store is not open"
        return self._expiry_task

    @property
    def new_expiry_event(self) -> asyncio.Event:
        """Get new expiry event."""
        assert self._new_expiry_event is not None, "Store is not open"
        return self._new_expiry_event

    async def _expiry_loop(self):
        """Loop to handle expired tasks."""
        assert self._ready_event
        self._ready_event.set()
        while True:
            if not self.expiry_heap:
                LOGGER.debug("No items, waiting until one is set")
                await self.new_expiry_event.wait()

            async with self.lock:
                self.new_expiry_event.clear()
                expire_time, key = self.expiry_heap[0]
                now = time.time()
                if now >= expire_time:
                    LOGGER.debug("Expiring key: %s", key)
                    heapq.heappop(self.expiry_heap)
                    self.store.pop(key, None)
                    continue
                else:
                    sleep_time = expire_time - now

            LOGGER.debug("Sleep: wait for %s to expire or new item", key)
            try:
                await asyncio.wait_for(
                    self.new_expiry_event.wait(),
                    sleep_time,
                )
            except asyncio.TimeoutError:
                LOGGER.debug("Awake: item ready to expire")
            else:
                LOGGER.debug("Awake: New item")

    async def set(self, key: str, value: Any, ttl: float):
        """Set a value."""
        async with self.lock:
            LOGGER.debug("Set: %s", key)
            self.store[key] = value
            expire_time = time.time() + ttl
            heapq.heappush(self.expiry_heap, (expire_time, key))
            self.new_expiry_event.set()

    async def get(self, key: str) -> Any:
        """Get a value."""
        async with self.lock:
            LOGGER.debug("Get: %s", key)
            return self.store.get(key)

    async def delete(self, key: str):
        """Delete a value."""
        async with self.lock:
            LOGGER.debug("Delete: %s", key)
            self.store.pop(key, None)
            self.new_expiry_event.set()

    async def close(self):
        """Close the store."""
        self.expiry_task.cancel()
        try:
            await self.expiry_task
        except asyncio.CancelledError:
            pass


async def main():
    """Example."""
    kv = TemporalKVStore()
    await kv.open()
    await kv.set("key1", "value1", 5)  # key1 will expire in 5 seconds
    await asyncio.sleep(1)
    await kv.set("key2", "value2", 5)  # key1 will expire in 5 seconds
    await asyncio.sleep(7)
    print(kv.expiry_heap)  # Should print None as key1 has expired

    await kv.close()


if __name__ == "__main__":
    asyncio.run(main())
