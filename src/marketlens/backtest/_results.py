from __future__ import annotations

from decimal import Decimal
from typing import Any

from marketlens.backtest._types import Fill, Order, SettlementRecord
from marketlens.backtest._portfolio import Portfolio

_FOUR = Decimal("0.0001")
_ZERO = Decimal("0")


class BacktestResult:
    def __init__(
        self,
        portfolio: Portfolio,
        orders: list[Order],
        settlements: list[SettlementRecord],
        equity_curve: list[dict],
        cash_rejected: int = 0,
    ) -> None:
        self._portfolio = portfolio
        self._orders = orders
        self._settlements = settlements
        self._equity_curve = equity_curve
        self._fills = [f for o in orders for f in o.fills]
        self.cash_rejected = cash_rejected

        initial = Decimal(portfolio.initial_cash)
        final_equity = Decimal(portfolio.equity)

        self.total_pnl = str((final_equity - initial).quantize(_FOUR))
        self.total_return = float((final_equity - initial) / initial) if initial else 0.0
        self.total_trades = len(self._fills)
        self.markets_traded = len({f.market_id for f in self._fills})
        self.total_fees = portfolio.total_fees

        # Fee drag
        total_volume = sum(Decimal(f.price) * Decimal(f.size) for f in self._fills)
        self.fee_drag_bps = (
            float(Decimal(portfolio.total_fees) / total_volume * 10000)
            if total_volume > 0
            else 0.0
        )

        # Win rate & profit factor (net of fees)
        net_pnls = [(s, Decimal(s.pnl) - Decimal(s.fees)) for s in settlements]
        wins = [n for _, n in net_pnls if n > 0]
        losses = [n for _, n in net_pnls if n < 0]
        self.win_rate = len(wins) / len(net_pnls) if net_pnls else 0.0

        gross_profit = sum(wins, _ZERO)
        gross_loss = abs(sum(losses, _ZERO))
        if gross_loss > 0:
            self.profit_factor = float(gross_profit / gross_loss)
        elif gross_profit > 0:
            self.profit_factor = float("inf")
        else:
            self.profit_factor = 0.0

        # Per-settlement returns (shared by Sharpe & Sortino)
        returns: list[float] = []
        if len(settlements) >= 2:
            for s in settlements:
                cb = Decimal(s.avg_entry_price) * Decimal(s.shares)
                if cb > 0:
                    returns.append(float((Decimal(s.pnl) - Decimal(s.fees)) / cb))

        # Sharpe ratio
        self.sharpe_ratio: float | None = None
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            std_r = var_r**0.5
            if std_r > 0:
                self.sharpe_ratio = mean_r / std_r

        # Sortino ratio
        self.sortino_ratio: float | None = None
        if len(returns) >= 2:
            neg_returns = [r for r in returns if r < 0]
            if neg_returns:
                mean_r = sum(returns) / len(returns)
                downside_var = sum(r**2 for r in neg_returns) / len(returns)
                downside_dev = downside_var**0.5
                if downside_dev > 0:
                    self.sortino_ratio = mean_r / downside_dev

        # Max drawdown & max drawdown duration
        if equity_curve:
            peak = Decimal(equity_curve[0]["equity"])
            max_dd = _ZERO
            dd_start: int | None = None
            max_dur = 0
            for point in equity_curve:
                eq = Decimal(point["equity"])
                if eq >= peak:
                    if dd_start is not None:
                        dur = point["t"] - dd_start
                        if dur > max_dur:
                            max_dur = dur
                        dd_start = None
                    peak = eq
                else:
                    if dd_start is None:
                        dd_start = point["t"]
                    dd = peak - eq
                    if dd > max_dd:
                        max_dd = dd
            # Handle still in drawdown at end
            if dd_start is not None:
                dur = equity_curve[-1]["t"] - dd_start
                if dur > max_dur:
                    max_dur = dur
            self.max_drawdown = float(max_dd / initial) if initial else 0.0
            self.max_drawdown_duration: int = max_dur
        else:
            self.max_drawdown = 0.0
            self.max_drawdown_duration = 0

        # Avg entry price
        buy_fills = [f for f in self._fills if f.side.value.startswith("BUY")]
        if buy_fills:
            total_cost = sum(Decimal(f.price) * Decimal(f.size) for f in buy_fills)
            total_size = sum(Decimal(f.size) for f in buy_fills)
            self.avg_entry_price = str((total_cost / total_size).quantize(_FOUR))
        else:
            self.avg_entry_price = "0.0000"

        # Expectancy (avg net PnL per settlement)
        if net_pnls:
            total_net = sum(n for _, n in net_pnls)
            self.expectancy = str((total_net / len(net_pnls)).quantize(_FOUR))
        else:
            self.expectancy = "0.0000"

        # Average win / average loss / payoff ratio
        self.avg_win = str((sum(wins) / len(wins)).quantize(_FOUR)) if wins else "0.0000"
        self.avg_loss = str((sum(losses) / len(losses)).quantize(_FOUR)) if losses else "0.0000"
        if losses:
            self.payoff_ratio = (
                float(abs(sum(wins) / len(wins)) / abs(sum(losses) / len(losses)))
                if wins
                else 0.0
            )
        else:
            self.payoff_ratio = float("inf") if wins else 0.0

        # Avg holding period (ms)
        if settlements:
            fill_first: dict[str, int] = {}
            for f in self._fills:
                if f.market_id not in fill_first or f.timestamp < fill_first[f.market_id]:
                    fill_first[f.market_id] = f.timestamp
            durations: list[int] = []
            for s in settlements:
                entry_t = fill_first.get(s.market_id)
                if entry_t is not None:
                    durations.append(s.resolved_at - entry_t)
            self.avg_holding_ms = sum(durations) // len(durations) if durations else 0
        else:
            self.avg_holding_ms = 0

        # Capital utilization
        if equity_curve and initial > 0:
            avg_cash = sum(Decimal(p["cash"]) for p in equity_curve) / len(equity_curve)
            self.capital_utilization = max(0.0, float(1 - avg_cash / initial))
        else:
            self.capital_utilization = 0.0

    def summary(self) -> dict[str, Any]:
        s: dict[str, Any] = {
            "total_pnl": self.total_pnl,
            "total_return": f"{self.total_return:.2%}",
            "win_rate": f"{self.win_rate:.2%}",
            "profit_factor": f"{self.profit_factor:.2f}",
            "max_drawdown": f"{self.max_drawdown:.2%}",
            "sharpe_ratio": (
                f"{self.sharpe_ratio:.2f}" if self.sharpe_ratio is not None else "N/A"
            ),
            "sortino_ratio": (
                f"{self.sortino_ratio:.2f}" if self.sortino_ratio is not None else "N/A"
            ),
            "expectancy": self.expectancy,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "payoff_ratio": f"{self.payoff_ratio:.2f}",
            "avg_holding_ms": self.avg_holding_ms,
            "capital_utilization": f"{self.capital_utilization:.1%}",
            "max_drawdown_duration_ms": self.max_drawdown_duration,
            "total_trades": self.total_trades,
            "markets_traded": self.markets_traded,
            "total_fees": self.total_fees,
            "fee_drag_bps": f"{self.fee_drag_bps:.1f}",
            "avg_entry_price": self.avg_entry_price,
        }
        if self.cash_rejected > 0:
            s["cash_rejected"] = self.cash_rejected
        return s

    def __repr__(self) -> str:
        s = self.summary()
        lines = ["BacktestResult("]
        for k, v in s.items():
            lines.append(f"  {k}={v}")
        lines.append(")")
        return "\n".join(lines)

    def trades_df(self):
        """All fills as a DataFrame."""
        import pandas as pd

        if not self._fills:
            return pd.DataFrame()
        rows = [
            {
                "t": f.timestamp,
                "market_id": f.market_id,
                "side": f.side.value,
                "price": float(f.price),
                "size": float(f.size),
                "fee": float(f.fee),
                "is_maker": f.is_maker,
            }
            for f in self._fills
        ]
        df = pd.DataFrame(rows)
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        return df.set_index("t")

    def orders_df(self):
        """All orders as a DataFrame."""
        import pandas as pd

        if not self._orders:
            return pd.DataFrame()
        rows = [
            {
                "t": o.submitted_at,
                "market_id": o.market_id,
                "side": o.side.value,
                "order_type": o.order_type.value,
                "size": float(o.size),
                "limit_price": float(o.limit_price) if o.limit_price else None,
                "status": o.status.value,
                "filled_size": float(o.filled_size),
                "avg_fill_price": (
                    float(o.avg_fill_price) if o.avg_fill_price else None
                ),
                "total_fees": float(o.total_fees),
            }
            for o in self._orders
        ]
        df = pd.DataFrame(rows)
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        return df.set_index("t")

    def settlements_df(self):
        """Per-market settlement results as a DataFrame."""
        import pandas as pd

        if not self._settlements:
            return pd.DataFrame()
        rows = [
            {
                "market_id": s.market_id,
                "series_id": s.series_id,
                "side": s.side.value,
                "shares": float(s.shares),
                "avg_entry_price": float(s.avg_entry_price),
                "settlement_price": float(s.settlement_price),
                "pnl": float(s.pnl),
                "fees": float(s.fees),
                "winning_outcome": s.winning_outcome,
                "resolved_at": s.resolved_at,
            }
            for s in self._settlements
        ]
        df = pd.DataFrame(rows)
        if "resolved_at" in df.columns:
            df["resolved_at"] = pd.to_datetime(df["resolved_at"], unit="ms", utc=True)
        return df

    def equity_df(self):
        """Equity curve as a DataFrame."""
        import pandas as pd

        if not self._equity_curve:
            return pd.DataFrame()
        df = pd.DataFrame(self._equity_curve)
        df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df["cash"] = df["cash"].astype(float)
        df["equity"] = df["equity"].astype(float)
        df["pnl"] = df["pnl"].astype(float)
        return df.set_index("t")

    def by_series(self) -> dict[str | None, dict]:
        """Per-series breakdown of backtest results.

        Returns a dict keyed by ``series_id`` (or ``None`` for unseries'd markets),
        with each value containing aggregated stats for that series.
        """
        from collections import defaultdict

        groups: dict[str | None, list[SettlementRecord]] = defaultdict(list)
        for s in self._settlements:
            groups[s.series_id].append(s)

        result: dict[str | None, dict] = {}
        for sid, settlements in groups.items():
            net_pnls = [(Decimal(s.pnl) - Decimal(s.fees)) for s in settlements]
            total_pnl = sum(net_pnls, _ZERO)
            total_fees = sum(Decimal(s.fees) for s in settlements)
            wins = [n for n in net_pnls if n > 0]
            losses = [n for n in net_pnls if n < 0]
            win_rate = len(wins) / len(net_pnls) if net_pnls else 0.0
            gross_profit = sum(wins, _ZERO)
            gross_loss = abs(sum(losses, _ZERO))
            if gross_loss > 0:
                profit_factor = float(gross_profit / gross_loss)
            elif gross_profit > 0:
                profit_factor = float("inf")
            else:
                profit_factor = 0.0

            market_ids = {s.market_id for s in settlements}
            total_trades = len([
                f for f in self._fills if f.market_id in market_ids
            ])

            expectancy = (
                str((total_pnl / len(net_pnls)).quantize(_FOUR)) if net_pnls else "0.0000"
            )
            avg_win = (
                str((sum(wins, _ZERO) / len(wins)).quantize(_FOUR)) if wins else "0.0000"
            )
            avg_loss = (
                str((sum(losses, _ZERO) / len(losses)).quantize(_FOUR))
                if losses
                else "0.0000"
            )
            if losses:
                payoff_ratio = (
                    float(
                        abs(sum(wins, _ZERO) / len(wins))
                        / abs(sum(losses, _ZERO) / len(losses))
                    )
                    if wins
                    else 0.0
                )
            else:
                payoff_ratio = float("inf") if wins else 0.0

            result[sid] = {
                "total_pnl": str(total_pnl.quantize(_FOUR)),
                "total_fees": str(total_fees.quantize(_FOUR)),
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "expectancy": expectancy,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "payoff_ratio": payoff_ratio,
                "markets_traded": len(market_ids),
                "total_trades": total_trades,
            }
        return result

    def to_dataframe(self):
        """Alias for ``settlements_df()`` (SDK convention)."""
        return self.settlements_df()
