from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from .errors import ProviderError, RateLimit

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.3
    max_retry_after: float = 60.0


DEFAULT_RETRY_POLICY = RetryPolicy()


def retry_delay(error: ProviderError, attempt: int, policy: RetryPolicy) -> float:
    if isinstance(error, RateLimit) and error.retry_after is not None:
        return min(max(0.0, error.retry_after), policy.max_retry_after)
    exponential = policy.base_delay * (2 ** (attempt - 1))
    delay = min(policy.max_delay, exponential)
    return max(0.0, delay * (1 + random.uniform(-policy.jitter, policy.jitter)))


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    attempt = 1
    while True:
        try:
            return await operation()
        except ProviderError as error:
            if not error.retryable or attempt >= policy.max_attempts:
                raise
            await sleep(retry_delay(error, attempt, policy))
            attempt += 1
