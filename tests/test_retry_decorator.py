import asyncio
import pytest

from core.decorators import retry_on_network


async def flaky(counter: list[int]):
    counter[0] += 1
    if counter[0] < 2:
        raise ConnectionError("boom")
    return "ok"


@pytest.mark.asyncio
async def test_retry_on_network_succeeds():
    counter = [0]

    @retry_on_network(attempts=3, base_delay=0.01)
    async def wrapped():
        return await flaky(counter)

    result = await wrapped()
    assert result == "ok"
    assert counter[0] == 2


@pytest.mark.asyncio
async def test_retry_on_network_exceeds():
    counter = [0]

    @retry_on_network(attempts=2, base_delay=0.01)
    async def wrapped():
        return await flaky(counter)

    with pytest.raises(ConnectionError):
        await wrapped()
