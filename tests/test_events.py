import asyncio
from collections.abc import AsyncGenerator

from agent_orc.events import ChangeNotifier, until_stopped


def test_a_stream_ends_as_the_server_stops_and_is_closed() -> None:
    async def scenario() -> list[str]:
        notifier = ChangeNotifier()
        stopping = asyncio.Event()
        stream = until_stopped(notifier.stream(), stopping)
        received = [await anext(stream)]
        await asyncio.to_thread(notifier.notify)
        received.append(await anext(stream))
        # Waiting for the next change when the stop comes.
        waiting = asyncio.ensure_future(anext(stream))
        await asyncio.sleep(0.01)
        stopping.set()
        try:
            await waiting
        except StopAsyncIteration:
            received.append("ended")
        # The inner stream was closed: it is no longer listening.
        assert not notifier._listeners
        return received

    assert asyncio.run(scenario()) == [": connected\n\n", "data: changed\n\n", "ended"]


def test_a_stream_that_ends_by_itself_ends_the_same() -> None:
    async def two() -> AsyncGenerator[str]:
        yield "one"
        yield "two"

    async def scenario() -> list[str]:
        return [event async for event in until_stopped(two(), asyncio.Event())]

    assert asyncio.run(scenario()) == ["one", "two"]
