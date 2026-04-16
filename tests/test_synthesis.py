from nodes.synthesis import synthesis_node


class DummyResponse:
    def __init__(self, content: str):
        self.content = content


def test_synthesis_parses_structured_output(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return DummyResponse(
                "BULL_THESIS:\nBull side with growth and margin expansion.\n\n"
                "BEAR_THESIS:\nBear side with valuation and execution risks."
            )

    monkeypatch.setattr("nodes.synthesis._llm", FakeLLM())

    out = synthesis_node(
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "news_headlines": ["h1", "h2"],
            "financial_data": "Revenue 100, Profit 20",
            "risk_factors": "Supply chain and regulation risk",
            "management_guidance": "Steady growth",
            "inspector_feedback": "Looks usable",
        }
    )

    assert "Bull side" in out["bull_thesis"]
    assert "Bear side" in out["bear_thesis"]


def test_synthesis_fallback_split_when_tags_missing(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return DummyResponse("first half text second half text")

    monkeypatch.setattr("nodes.synthesis._llm", FakeLLM())

    out = synthesis_node({"ticker": "AAPL"})
    assert out["bull_thesis"]
    assert out["bear_thesis"]
