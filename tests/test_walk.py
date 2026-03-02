import httpx

from conftest import BASE_URL, SAMPLE_MARKET, SAMPLE_CANDLE, SAMPLE_ORDERBOOK, SAMPLE_SERIES
from marketlens.helpers.walk import MarketSlot


def _market_with(overrides):
    return {**SAMPLE_MARKET, **overrides}


def _mock_series_resolve(mock_api):
    """Mock the /series/btc-daily GET used by _resolve()."""
    mock_api.get("/series/btc-daily").mock(
        return_value=httpx.Response(200, json=SAMPLE_SERIES)
    )


class TestSeriesWalk:
    def test_walk_yields_slots_in_order(self, mock_api, client):
        """walk() should yield MarketSlot objects in chronological order."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 2000})
        m2 = _market_with({"id": "m2", "open_time": 1500, "close_time": 2500})
        m3 = _market_with({"id": "m3", "open_time": 2000, "close_time": 3000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1, m2, m3],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        slots = list(client.series.walk("btc-daily"))
        assert len(slots) == 3
        assert isinstance(slots[0], MarketSlot)
        assert slots[0].market.id == "m1"
        assert slots[0].index == 0
        assert slots[0].prev_market is None
        assert slots[0].next_market.id == "m2"

        assert slots[1].prev_market.id == "m1"
        assert slots[1].next_market.id == "m3"

        assert slots[2].prev_market.id == "m2"
        assert slots[2].next_market is None

    def test_slot_overlap_with_prev(self, mock_api, client):
        """Detect overlapping markets in a rolling series."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 6000})
        m2 = _market_with({"id": "m2", "open_time": 4000, "close_time": 9000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1, m2],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        slots = list(client.series.walk("btc-daily"))
        assert slots[0].overlap_with_prev is None  # first market
        assert slots[1].overlap_with_prev == 2000  # m1 closes 6000, m2 opens 4000

    def test_slot_gap_from_prev(self, mock_api, client):
        """Detect gaps between markets."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 2000})
        m2 = _market_with({"id": "m2", "open_time": 5000, "close_time": 6000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1, m2],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        slots = list(client.series.walk("btc-daily"))
        assert slots[1].gap_from_prev == 3000  # m1 closes 2000, m2 opens 5000

    def test_slot_contiguous_markets(self, mock_api, client):
        """Contiguous markets (close == next open) should report 0 gap and 0 overlap."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 2000})
        m2 = _market_with({"id": "m2", "open_time": 2000, "close_time": 3000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1, m2],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        slots = list(client.series.walk("btc-daily"))
        assert slots[1].overlap_with_prev == 0
        assert slots[1].gap_from_prev == 0

    def test_slot_candles(self, mock_api, client):
        """Slot.candles() should load candles for the market."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 6000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1],
                "meta": {"cursor": None, "has_more": False},
            })
        )
        mock_api.get("/markets/m1/candles").mock(
            return_value=httpx.Response(200, json={
                "data": [SAMPLE_CANDLE],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        slots = list(client.series.walk("btc-daily"))
        candles = slots[0].candles("1m").to_list()
        assert len(candles) == 1
        assert candles[0].trade_count == 47

    def test_slot_orderbook(self, mock_api, client):
        """Slot.orderbook() should load the book for the market."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "open_time": 1000, "close_time": 6000})

        mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1],
                "meta": {"cursor": None, "has_more": False},
            })
        )
        mock_api.get("/markets/m1/orderbook").mock(
            return_value=httpx.Response(200, json=SAMPLE_ORDERBOOK)
        )

        slots = list(client.series.walk("btc-daily"))
        book = slots[0].orderbook()
        assert book.best_bid == "0.6500"

    def test_walk_with_status_filter(self, mock_api, client):
        """Walk should pass filter params through."""
        _mock_series_resolve(mock_api)
        m1 = _market_with({"id": "m1", "status": "resolved"})

        route = mock_api.get("/series/btc-daily/markets").mock(
            return_value=httpx.Response(200, json={
                "data": [m1],
                "meta": {"cursor": None, "has_more": False},
            })
        )

        list(client.series.walk("btc-daily", status="resolved"))
        # Check that status param was sent
        assert route.call_count == 1
