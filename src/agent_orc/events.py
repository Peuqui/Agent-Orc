"""Tells open pages that something changed, as server-sent events (they then fetch it again)."""

import asyncio
from collections.abc import AsyncGenerator

# A comment line now and then keeps proxies from closing a quiet stream.
KEEP_ALIVE_SECONDS = 25


class ChangeNotifier:
    """Handlers run in worker threads, the streams in the event loop: notify() hands over to it."""

    def __init__(self) -> None:
        self._listeners: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[None]]] = set()

    def subscribe(self) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue[None]]:
        listener = (asyncio.get_running_loop(), asyncio.Queue[None]())
        self._listeners.add(listener)
        return listener

    def unsubscribe(self, listener: tuple[asyncio.AbstractEventLoop, asyncio.Queue[None]]) -> None:
        self._listeners.discard(listener)

    def notify(self) -> None:
        for loop, queue in list(self._listeners):
            loop.call_soon_threadsafe(queue.put_nowait, None)

    async def stream(self) -> AsyncGenerator[str]:
        listener = self.subscribe()
        queue = listener[1]
        try:
            # Opens the stream at once, so the page knows it is connected.
            yield ": connected\n\n"
            while True:
                try:
                    await asyncio.wait_for(queue.get(), KEEP_ALIVE_SECONDS)
                    yield "data: changed\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            self.unsubscribe(listener)
