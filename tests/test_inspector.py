from nodes.inspector import inspector_node


class DummyResponse:
    def __init__(self, content: str):
        self.content = content


def test_inspector_forced_pass_when_max_retries_reached():
    state = {
        "search_attempts": 3,
        "news_headlines": [],
    }

    out = inspector_node(state)

    assert out["inspector_passed"] is True
    assert "Forced pass after 3 search attempts" in out["inspector_feedback"]


def test_inspector_fails_when_headlines_too_few(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            raise AssertionError("LLM should not be called when headlines are insufficient.")

    monkeypatch.setattr("nodes.inspector._llm", FakeLLM())

    state = {
        "search_attempts": 0,
        "news_headlines": ["only one"],
    }
    out = inspector_node(state)

    assert out["inspector_passed"] is False
    assert "minimum is 2" in out["inspector_feedback"]


def test_inspector_uses_llm_verdict_for_non_forced_flow(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return DummyResponse(
                "BULL_DATA: yes\n"
                "BEAR_DATA: yes\n"
                "NUMBERS_OK: yes\n"
                "VERDICT: fail\n"
                "REASON: Missing enough evidence."
            )

    monkeypatch.setattr("nodes.inspector._llm", FakeLLM())

    state = {
        "search_attempts": 0,
        "news_headlines": ["h1", "h2", "h3"],
        "financial_data": "Revenue 100, Profit 20",
        "risk_factors": "Supply chain risk",
        "management_guidance": "Guidance steady growth",
    }

    out = inspector_node(state)

    assert out["inspector_passed"] is False
    assert "VERDICT: fail" in out["inspector_feedback"]
