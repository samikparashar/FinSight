from nodes.writer import writer_node


class DummyResponse:
    def __init__(self, content: str):
        self.content = content


def test_writer_returns_final_report(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return DummyResponse("# Sample Report\n\nFinal text.")

    monkeypatch.setattr("nodes.writer._llm", FakeLLM())

    out = writer_node(
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "financial_data": "Revenue 100",
            "news_headlines": ["headline 1", "headline 2"],
            "bull_thesis": "Bull thesis",
            "bear_thesis": "Bear thesis",
            "risk_factors": "Risk factors",
            "management_guidance": "Guidance",
        }
    )

    assert out["final_report"].startswith("# Sample Report")
    assert "Final text." in out["final_report"]
