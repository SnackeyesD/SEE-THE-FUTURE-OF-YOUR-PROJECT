from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx

from .errors import ProviderDown, ProviderError, map_http_error
from .retry import DEFAULT_RETRY_POLICY, RetryPolicy, retry_delay


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _http_error(response: httpx.Response, provider: str, body: str) -> ProviderError:
    return map_http_error(
        response.status_code,
        body,
        provider=provider,
        retry_after=_retry_after(response),
    )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Any:
    attempt = 1
    while True:
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )
        except httpx.HTTPError as error:
            failure: ProviderError = ProviderDown(
                f"connexion au fournisseur impossible: {error}",
                provider=provider,
            )
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError as error:
                    raise ProviderDown(
                        "réponse JSON invalide du fournisseur",
                        provider=provider,
                    ) from error
            failure = _http_error(response, provider, response.text)
        if not failure.retryable or attempt >= policy.max_attempts:
            raise failure
        await sleep(retry_delay(failure, attempt, policy))
        attempt += 1


async def open_stream(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> httpx.Response:
    attempt = 1
    while True:
        try:
            request = client.build_request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
            )
            response = await client.send(request, stream=True)
        except httpx.HTTPError as error:
            failure: ProviderError = ProviderDown(
                f"connexion au fournisseur impossible: {error}",
                provider=provider,
            )
        else:
            if response.status_code < 400:
                return response
            body = (await response.aread()).decode("utf-8", errors="replace")
            await response.aclose()
            failure = _http_error(response, provider, body)
        if not failure.retryable or attempt >= policy.max_attempts:
            raise failure
        await sleep(retry_delay(failure, attempt, policy))
        attempt += 1


async def iter_sse(response: httpx.Response) -> AsyncIterator[str]:
    try:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            if data:
                yield data
    finally:
        await response.aclose()
