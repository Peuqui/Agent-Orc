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


async def until_stopped[T](events: AsyncGenerator[T], stopping: asyncio.Event) -> AsyncGenerator[T]:
    """`events` until `stopping` is set. A live stream never ends by itself: without this, a stop
    of the server waits for it in vain and then cancels it (see cli.Server)."""
    stop = asyncio.ensure_future(stopping.wait())
    following: asyncio.Future[T] | None = None
    try:
        while True:
            following = asyncio.ensure_future(anext(events))
            await asyncio.wait({following, stop}, return_when=asyncio.FIRST_COMPLETED)
            if not following.done():
                return
            try:
                event = following.result()
            except StopAsyncIteration:
                return
            yield event
    finally:
        stop.cancel()
        if following is not None and not following.done():
            # Still waiting for the next event when the stop came or the page went: cancelling
            # that ends the stream, which cleans up in it. Not waited for: a page that went leaves
            # this in Starlette's cancelled scope, where every await is cancelled again.
            following.cancel()
        else:
            await events.aclose()
