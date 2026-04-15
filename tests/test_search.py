from nodes.search import search_node


def test_search_node_success(monkeypatch):
    def fake_search(**kwargs):
        return {
            "answer": "Strong momentum after earnings.",
            "results": [
                {
                    "title": "Company beats estimates",
                    "content": "Revenue and EPS above consensus.",
                    "url": "https://example.com/a",
                    "score": 0.92,
                },
                {
                    "title": "Low quality result",
                    "content": "Should be filtered out.",
                    "url": "https://example.com/b",
                    "score": 0.10,
                },
            ],
        }

    monkeypatch.setattr("nodes.search._client.search", fake_search)

    out = search_node({"ticker": "AAPL", "company_name": "Apple", "search_attempts": 0})

    assert out["search_attempts"] == 1
    assert out["search_query_used"]
    assert len(out["news_headlines"]) == 2
    assert out["news_headlines"][0].startswith("[Summary]")


def test_search_node_handles_exception(monkeypatch):
    def fake_search(**kwargs):
        raise RuntimeError("tavily down")

    monkeypatch.setattr("nodes.search._client.search", fake_search)

    out = search_node({"ticker": "AAPL", "search_attempts": 1})

    assert out["search_attempts"] == 2
    assert "Search failed" in out["news_headlines"][0]
