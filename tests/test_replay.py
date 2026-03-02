import pytest

from marketlens import OrderBookReplay, SnapshotEvent, DeltaEvent, TradeEvent, PriceLevel


def _make_snapshot(t, bids, asks, is_reseed=False):
    return SnapshotEvent(
        t=t,
        is_reseed=is_reseed,
        bids=[PriceLevel(price=p, size=s) for p, s in bids],
        asks=[PriceLevel(price=p, size=s) for p, s in asks],
    )


def _make_delta(t, price, size, side):
    return DeltaEvent(t=t, price=price, size=size, side=side)


def _make_trade(t, trade_id, price, size, side):
    return TradeEvent(t=t, id=trade_id, price=price, size=size, side=side)


class TestOrderBookReplay:
    def test_snapshot_only(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
        ]
        results = list(OrderBookReplay(events, market_id="m1"))
        assert len(results) == 1
        event, book = results[0]
        assert book.best_bid == "0.6500"
        assert book.best_ask == "0.6700"
        assert book.spread == "0.0200"

    def test_delta_updates_book(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_delta(1001, "0.6500", "350.0000", "BUY"),
        ]
        results = list(OrderBookReplay(events, market_id="m1"))
        assert len(results) == 2
        _, book = results[1]
        assert book.bids[0].size == "350.0000"

    def test_delta_removes_level(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000"), ("0.6400", "100.0000")], [("0.6700", "100.0000")]),
            _make_delta(1001, "0.6500", "0", "BUY"),
        ]
        results = list(OrderBookReplay(events, market_id="m1"))
        _, book = results[1]
        assert book.best_bid == "0.6400"
        assert book.bid_levels == 1

    def test_trade_does_not_change_book(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_trade(1001, "t1", "0.6700", "50.0000", "BUY"),
        ]
        results = list(OrderBookReplay(events, market_id="m1"))
        assert len(results) == 2
        _, book_after_snap = results[0]
        _, book_after_trade = results[1]
        assert book_after_snap.bids == book_after_trade.bids
        assert book_after_snap.asks == book_after_trade.asks

    def test_second_snapshot_replaces(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_delta(1001, "0.6500", "350.0000", "BUY"),
            _make_snapshot(2000, [("0.6600", "180.0000")], [("0.6800", "90.0000")]),
        ]
        results = list(OrderBookReplay(events, market_id="m1"))
        _, book = results[2]
        assert book.best_bid == "0.6600"
        assert book.best_ask == "0.6800"

    def test_full_sequence(self):
        """Replicate the API doc example sequence."""
        events = [
            _make_snapshot(
                1700000060000,
                [("0.6500", "200.0000"), ("0.6400", "150.0000"), ("0.6300", "500.0000")],
                [("0.6700", "100.0000"), ("0.6800", "250.0000")],
            ),
            _make_delta(1700000061234, "0.6500", "350.0000", "BUY"),
            _make_trade(1700000062500, "t1", "0.6700", "100.0000", "BUY"),
            _make_delta(1700000062891, "0.6300", "0", "BUY"),
            _make_snapshot(
                1700000120000,
                [("0.6600", "180.0000"), ("0.6500", "350.0000")],
                [("0.6700", "90.0000"), ("0.6800", "300.0000")],
            ),
        ]

        results = list(OrderBookReplay(events, market_id="m1", platform="polymarket"))
        assert len(results) == 5

        _, book1 = results[1]
        assert book1.bids[0].price == "0.6500"
        assert book1.bids[0].size == "350.0000"

        _, book3 = results[3]
        assert book3.bid_levels == 2

        _, book4 = results[4]
        assert book4.best_bid == "0.6600"
        assert book4.bid_levels == 2

    def test_delta_before_snapshot_raises(self):
        events = [
            _make_delta(1000, "0.6500", "100.0000", "BUY"),
        ]
        with pytest.raises(ValueError, match="delta before any snapshot"):
            list(OrderBookReplay(events))

    def test_trade_before_snapshot_raises(self):
        events = [
            _make_trade(1000, "t1", "0.6500", "100.0000", "BUY"),
        ]
        with pytest.raises(ValueError, match="trade before any snapshot"):
            list(OrderBookReplay(events))


class TestReplayToDataFrame:
    def test_to_dataframe_basic(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_delta(2000, "0.6500", "350.0000", "BUY"),
        ]
        df = OrderBookReplay(events, market_id="m1").to_dataframe()
        assert len(df) == 2
        assert "best_bid" in df.columns
        assert "spread" in df.columns
        assert "imbalance" in df.columns
        assert df.index.name == "t"
        # Values should be float, not string
        assert df["best_bid"].dtype == float
        assert df["spread"].dtype == float

    def test_to_dataframe_with_trades(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_trade(2000, "t1", "0.6700", "50.0000", "BUY"),
        ]
        df = OrderBookReplay(events, market_id="m1").to_dataframe()
        assert len(df) == 2
        # Trade row should have trade columns
        assert "trade_price" in df.columns
        assert "trade_side" in df.columns

    def test_to_dataframe_empty(self):
        df = OrderBookReplay([], market_id="m1").to_dataframe()
        assert len(df) == 0

    def test_to_dataframe_has_microprice_columns(self):
        events = [
            _make_snapshot(1000, [("0.6500", "200.0000")], [("0.6700", "100.0000")]),
            _make_delta(2000, "0.6500", "350.0000", "BUY"),
        ]
        df = OrderBookReplay(events, market_id="m1").to_dataframe()
        assert "weighted_midpoint" in df.columns
        assert "spread_bps" in df.columns
        assert df["weighted_midpoint"].dtype == float
        assert df["spread_bps"].dtype == float
        assert df["weighted_midpoint"].notna().all()
        assert df["spread_bps"].notna().all()
