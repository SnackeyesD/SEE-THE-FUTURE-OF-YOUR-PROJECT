from __future__ import annotations

import pytest

from providers import AuthError, ProviderDown, RateLimit, RetryPolicy, run_with_retry


async def test_retries_rate_limit_with_header_delay() -> None:
    delays: list[float] = []
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RateLimit("slow down", retry_after=2.5)
        return "ok"

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    result = await run_with_retry(
        operation,
        policy=RetryPolicy(max_attempts=2, jitter=0),
        sleep=fake_sleep,
    )
    assert result == "ok"
    assert delays == [2.5]
    assert attempts == 2


async def test_does_not_retry_auth_error() -> None:
    async def operation() -> str:
        raise AuthError("bad key")

    with pytest.raises(AuthError):
        await run_with_retry(operation)


async def test_gives_up_after_max_attempts() -> None:
    async def operation() -> str:
        raise ProviderDown("offline")

    async def fake_sleep(_delay: float) -> None:
        return None

    with pytest.raises(ProviderDown):
        await run_with_retry(
            operation,
            policy=RetryPolicy(max_attempts=2, jitter=0),
            sleep=fake_sleep,
        )
