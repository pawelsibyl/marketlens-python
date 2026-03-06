from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

_FOUR = Decimal("0.0001")
_ZERO = Decimal("0")
_ONE = Decimal("1")


class FeeModel(ABC):
    @abstractmethod
    def calculate(self, price: Decimal, size: Decimal, is_maker: bool) -> Decimal: ...


class PolymarketFeeModel(FeeModel):
    """``fee_per_share = price * (1 - price) * rate``; taker only (maker = 0)."""

    def __init__(self, rate_bps: int = 0) -> None:
        self._rate = Decimal(rate_bps) / Decimal(10_000)

    def calculate(self, price: Decimal, size: Decimal, is_maker: bool) -> Decimal:
        if is_maker:
            return _ZERO
        fee_per_share = price * (_ONE - price) * self._rate
        return (fee_per_share * size).quantize(_FOUR)


class ZeroFeeModel(FeeModel):
    """Always returns 0."""

    def calculate(self, price: Decimal, size: Decimal, is_maker: bool) -> Decimal:
        return _ZERO


class FlatFeeModel(FeeModel):
    """Fixed fee per share."""

    def __init__(self, fee_per_share: Decimal) -> None:
        self._fee = fee_per_share

    def calculate(self, price: Decimal, size: Decimal, is_maker: bool) -> Decimal:
        return (self._fee * size).quantize(_FOUR)
