from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import httpx

from marketlens._constants import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, VERSION
from marketlens.exceptions import (
    APIError,
    ConnectionError,
    RateLimitError,
    TimeoutError,
    _CODE_TO_EXCEPTION,
    _STATUS_TO_EXCEPTION,
)


def _coerce_timestamp(value: Any) -> Any:
    """Convert datetime to ms epoch; pass through ints and strings."""
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return value


def _prepare_params(params: dict[str, Any]) -> dict[str, Any]:
    """Clean None values and coerce timestamps."""
    out: dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        v = _coerce_timestamp(v)
        if isinstance(v, bool):
            out[k] = str(v).lower()
        else:
            out[k] = v
    return out


def _raise_for_error(response: httpx.Response) -> None:
    """Parse API error JSON and raise the appropriate exception."""
    if response.status_code < 400:
        return

    try:
        body = response.json()
        error = body.get("error", {})
        code = error.get("code", str(response.status_code))
        message = error.get("message", response.text)
    except Exception:
        code = str(response.status_code)
        message = response.text

    # Pick exception class: prefer code-based mapping, fall back to status
    exc_cls = _CODE_TO_EXCEPTION.get(code) or _STATUS_TO_EXCEPTION.get(response.status_code, APIError)

    if exc_cls is RateLimitError:
        retry_after_raw = response.headers.get("Retry-After")
        retry_after = int(retry_after_raw) if retry_after_raw else None
        raise RateLimitError(response.status_code, code, message, retry_after=retry_after)

    raise exc_cls(response.status_code, code, message)


def _should_retry(response: httpx.Response) -> bool:
    return response.status_code == 429 or response.status_code >= 500


def _user_agent() -> str:
    return f"marketlens-python/{VERSION}"


class SyncHTTPClient:
    """Synchronous HTTP transport with auth, retry, and error mapping."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key or os.environ.get("MARKETLENS_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "User-Agent": _user_agent(),
                "Authorization": f"Bearer {self.api_key}",
            },
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if "params" in kwargs:
            kwargs["params"] = _prepare_params(kwargs["params"])

        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = ConnectionError(str(exc))
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise last_exc from exc

            if _should_retry(response) and attempt < self.max_retries:
                delay = 2**attempt
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        delay = max(delay, int(retry_after))
                time.sleep(delay)
                continue

            _raise_for_error(response)
            return response.json()

        # Should not reach here, but just in case
        if last_exc:
            raise last_exc

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params or {})

    def close(self) -> None:
        self._client.close()


class AsyncHTTPClient:
    """Asynchronous HTTP transport with auth, retry, and error mapping."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key or os.environ.get("MARKETLENS_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "User-Agent": _user_agent(),
                "Authorization": f"Bearer {self.api_key}",
            },
        )

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        import asyncio

        if "params" in kwargs:
            kwargs["params"] = _prepare_params(kwargs["params"])

        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.TimeoutException as exc:
                last_exc = TimeoutError(str(exc))
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise last_exc from exc
            except httpx.ConnectError as exc:
                last_exc = ConnectionError(str(exc))
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise last_exc from exc

            if _should_retry(response) and attempt < self.max_retries:
                delay = 2**attempt
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        delay = max(delay, int(retry_after))
                await asyncio.sleep(delay)
                continue

            _raise_for_error(response)
            return response.json()

        if last_exc:
            raise last_exc

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request("GET", path, params=params or {})

    async def close(self) -> None:
        await self._client.aclose()
