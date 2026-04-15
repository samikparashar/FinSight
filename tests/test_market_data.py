import importlib
import sys
from types import ModuleType


class FakeTicker:
    def __init__(self, _ticker: str):
        self.info = {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 30.5,
            "forwardPE": 28.1,
            "priceToBook": 40.2,
            "enterpriseToEbitda": 22.0,
            "revenueGrowth": 0.08,
            "earningsGrowth": 0.10,
            "profitMargins": 0.24,
            "grossMargins": 0.46,
            "debtToEquity": 120.0,
            "currentRatio": 1.1,
            "freeCashflow": 100_000_000_000,
            "totalCash": 70_000_000_000,
            "dividendYield": 0.005,
            "payoutRatio": 0.15,
            "beta": 1.2,
            "fiftyTwoWeekHigh": 250.0,
            "fiftyTwoWeekLow": 150.0,
            "currentPrice": 210.0,
        }


def test_market_data_node_returns_expected_fields(monkeypatch):
    fake_yfinance = ModuleType("yfinance")
    fake_yfinance.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    market_data = importlib.import_module("nodes.market_data")
    importlib.reload(market_data)

    out = market_data.market_data_node({"ticker": "AAPL"})

    assert out["company_name"] == "Apple Inc."
    assert out["sector"] == "Technology"
    assert out["market_cap"] == 3_000_000_000_000
    assert "COMPANY OVERVIEW" in out["financial_data"]
    assert "AAPL" in out["financial_data"]
