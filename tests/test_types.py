from marketlens import (
    Market,
    Event,
    Series,
    Trade,
    Candle,
    OrderBook,
    PriceLevel,
    BookMetrics,
    SnapshotEvent,
    DeltaEvent,
    TradeEvent,
)
from conftest import (
    SAMPLE_MARKET,
    SAMPLE_EVENT,
    SAMPLE_SERIES,
    SAMPLE_TRADE,
    SAMPLE_CANDLE,
    SAMPLE_ORDERBOOK,
    SAMPLE_BOOK_METRICS,
)


class TestTypesParsing:
    def test_market(self):
        m = Market.model_validate(SAMPLE_MARKET)
        assert m.id == "abc-123"
        assert m.outcomes[0].last_price == "0.6500"
        assert m.status == "active"

    def test_event(self):
        e = Event.model_validate(SAMPLE_EVENT)
        assert e.market_count == 3

    def test_series(self):
        s = Series.model_validate(SAMPLE_SERIES)
        assert s.is_rolling is True
        assert s.market_count == 365

    def test_trade(self):
        t = Trade.model_validate(SAMPLE_TRADE)
        assert t.side == "BUY"
        assert t.fee_rate_bps == "50"

    def test_candle(self):
        c = Candle.model_validate(SAMPLE_CANDLE)
        assert c.trade_count == 47
        assert c.vwap == "0.6537"

    def test_orderbook(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        assert ob.bid_levels == 3
        assert ob.best_bid == "0.6500"
        assert len(ob.asks) == 3

    def test_book_metrics(self):
        bm = BookMetrics.model_validate(SAMPLE_BOOK_METRICS)
        assert bm.spread == "0.0200"

    def test_snapshot_event(self):
        raw = {
            "type": "snapshot",
            "t": 1700000060000,
            "is_reseed": False,
            "bids": [{"price": "0.6500", "size": "200.0000"}],
            "asks": [{"price": "0.6700", "size": "100.0000"}],
        }
        e = SnapshotEvent.model_validate(raw)
        assert e.type == "snapshot"
        assert len(e.bids) == 1

    def test_delta_event(self):
        raw = {"type": "delta", "t": 1700000061234, "price": "0.6500", "size": "350.0000", "side": "BUY"}
        e = DeltaEvent.model_validate(raw)
        assert e.side == "BUY"

    def test_trade_event(self):
        raw = {"type": "trade", "t": 1700000062500, "id": "01XYZ", "price": "0.6700", "size": "100.0000", "side": "BUY"}
        e = TradeEvent.model_validate(raw)
        assert e.id == "01XYZ"


class TestOrderBookHelpers:
    def test_impact_buy(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Buy 100 at 0.6700 (fills entire first ask level)
        avg = ob.impact("BUY", "100.0000")
        assert avg == "0.6700"

    def test_impact_buy_multi_level(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Buy 350: 100 @ 0.6700 + 250 @ 0.6800
        avg = ob.impact("BUY", "350.0000")
        assert avg is not None
        assert float(avg) > 0.67

    def test_impact_sell(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Sell 200 at best bid 0.6500
        avg = ob.impact("SELL", "200.0000")
        assert avg == "0.6500"

    def test_impact_insufficient_liquidity(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Try to buy more than total ask depth (750)
        avg = ob.impact("BUY", "1000.0000")
        # Should still return an avg (partial fill)
        assert avg is not None

    def test_depth_within(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # All levels within 0.05 of midpoint 0.66
        bid_d, ask_d = ob.depth_within("0.0500")
        assert bid_d == "850.0000"
        assert ask_d == "750.0000"

    def test_depth_within_narrow(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Only levels within 0.01 of mid: bid 0.65, ask 0.67
        bid_d, ask_d = ob.depth_within("0.0100")
        assert bid_d == "200.0000"
        assert ask_d == "100.0000"

    def test_slippage(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # Midpoint 0.6600, buy 100 fills at 0.6700 exactly
        slip = ob.slippage("BUY", "100.0000")
        assert slip == "0.0100"

    def test_imbalance(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # bid_depth=850, ask_depth=750 → (850-750)/(850+750) = 100/1600 = 0.0625
        imb = ob.imbalance()
        assert imb is not None
        assert abs(imb - 0.0625) < 0.001

    def test_imbalance_empty_book(self):
        ob = OrderBook(
            market_id="x", platform="p", as_of=0,
            bids=[], asks=[],
            bid_depth="0.0000", ask_depth="0.0000",
            bid_levels=0, ask_levels=0,
        )
        assert ob.imbalance() is None

    def test_weighted_midpoint_single_level(self):
        ob = OrderBook.model_validate(SAMPLE_ORDERBOOK)
        # n=1: best bid 0.6500 (size 200), best ask 0.6700 (size 100)
        # wmid = (0.6500*100 + 0.6700*200) / (200+100) = (65+134)/300 = 199/300
        wmid = ob.weighted_midpoint(n=1)
        assert wmid is not None
        val = float(wmid)
        # Should be closer to best ask (heavier bid side weight)
        assert 0.6500 < val < 0.6700

    def test_weighted_midpoint_empty_side(self):
        ob = OrderBook(
            market_id="x", platform="p", as_of=0,
            bids=[], asks=[PriceLevel(price="0.5000", size="100.0000")],
            bid_levels=0, ask_levels=1,
        )
        assert ob.weighted_midpoint() is None
