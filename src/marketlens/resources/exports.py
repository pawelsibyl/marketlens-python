from __future__ import annotations

import datetime
from pathlib import Path
from typing import Literal

from marketlens._base import AsyncHTTPClient, SyncHTTPClient

Table = Literal["snapshots", "deltas"]


def _date_range(after: str, before: str) -> list[str]:
    """Generate YYYY-MM-DD strings from after (inclusive) to before (exclusive)."""
    start = datetime.date.fromisoformat(after)
    end = datetime.date.fromisoformat(before)
    dates: list[str] = []
    d = start
    while d < end:
        dates.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return dates


class Exports:
    def __init__(self, client: SyncHTTPClient) -> None:
        self._client = client

    def download(
        self,
        market_id: str,
        *,
        table: Table,
        date: str,
        path: str | Path = ".",
    ) -> Path:
        """Download a day's Parquet export for a market.

        Args:
            market_id: Market UUID.
            table: ``"snapshots"`` or ``"deltas"``.
            date: Date string (YYYY-MM-DD). Must be before today.
            path: Directory to save the file in.

        Returns:
            Path to the downloaded Parquet file.
        """
        dest = Path(path) / f"{table}-{market_id}-{date}.parquet"
        return self._client.download(
            f"/markets/{market_id}/export",
            dest,
            params={"table": table, "date": date},
        )

    def download_range(
        self,
        market_id: str,
        *,
        table: Table,
        after: str,
        before: str,
        path: str | Path = ".",
    ) -> list[Path]:
        """Download multiple days of Parquet exports for a market.

        Args:
            market_id: Market UUID.
            table: ``"snapshots"`` or ``"deltas"``.
            after: Start date inclusive (YYYY-MM-DD).
            before: End date exclusive (YYYY-MM-DD).
            path: Directory to save files in.

        Returns:
            List of paths to downloaded Parquet files.
        """
        files: list[Path] = []
        for date in _date_range(after, before):
            files.append(self.download(market_id, table=table, date=date, path=path))
        return files


class AsyncExports:
    def __init__(self, client: AsyncHTTPClient) -> None:
        self._client = client

    async def download(
        self,
        market_id: str,
        *,
        table: Table,
        date: str,
        path: str | Path = ".",
    ) -> Path:
        """Download a day's Parquet export for a market.

        Args:
            market_id: Market UUID.
            table: ``"snapshots"`` or ``"deltas"``.
            date: Date string (YYYY-MM-DD). Must be before today.
            path: Directory to save the file in.

        Returns:
            Path to the downloaded Parquet file.
        """
        dest = Path(path) / f"{table}-{market_id}-{date}.parquet"
        return await self._client.download(
            f"/markets/{market_id}/export",
            dest,
            params={"table": table, "date": date},
        )

    async def download_range(
        self,
        market_id: str,
        *,
        table: Table,
        after: str,
        before: str,
        path: str | Path = ".",
    ) -> list[Path]:
        """Download multiple days of Parquet exports for a market.

        Args:
            market_id: Market UUID.
            table: ``"snapshots"`` or ``"deltas"``.
            after: Start date inclusive (YYYY-MM-DD).
            before: End date exclusive (YYYY-MM-DD).
            path: Directory to save files in.

        Returns:
            List of paths to downloaded Parquet files.
        """
        files: list[Path] = []
        for date in _date_range(after, before):
            files.append(await self.download(market_id, table=table, date=date, path=path))
        return files
