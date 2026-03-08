from __future__ import annotations

from typing import Any

from marketlens._base import AsyncHTTPClient, SyncHTTPClient
from marketlens._pagination import AsyncPageIterator, SyncPageIterator
from marketlens.types.reference import ReferenceCandle


class Reference:
    def __init__(self, client: SyncHTTPClient) -> None:
        self._client = client

    def candles(self, symbol: str, **params: Any) -> SyncPageIterator[ReferenceCandle]:
        params["symbol"] = symbol
        return SyncPageIterator(self._client, "/reference/candles", params, ReferenceCandle)


class AsyncReference:
    def __init__(self, client: AsyncHTTPClient) -> None:
        self._client = client

    def candles(self, symbol: str, **params: Any) -> AsyncPageIterator[ReferenceCandle]:
        params["symbol"] = symbol
        return AsyncPageIterator(self._client, "/reference/candles", params, ReferenceCandle)
