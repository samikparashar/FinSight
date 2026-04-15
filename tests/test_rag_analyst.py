from types import SimpleNamespace

from nodes.rag_analyst import rag_analyst_node


class FakeVectorStore:
    def similarity_search(self, query, k):
        if "risk" in query.lower():
            return [SimpleNamespace(page_content="Risk: supply chain concentration.")]
        return [SimpleNamespace(page_content="Guidance: expand services and AI features.")]


def test_rag_analyst_node_without_vectorstore():
    out = rag_analyst_node({"ticker": "AAPL", "vectorstore": None})
    assert "unavailable" in out["risk_factors"].lower()
    assert "unavailable" in out["management_guidance"].lower()


def test_rag_analyst_node_with_mocked_llm(monkeypatch):
    def fake_map(chunks, task_description, company):
        return [f"{company} | {task_description} | {len(chunks)} chunks"]

    def fake_reduce(summaries, task_description, company):
        return f"{company}: {task_description} :: {summaries[0]}"

    monkeypatch.setattr("nodes.rag_analyst._map_chunks", fake_map)
    monkeypatch.setattr("nodes.rag_analyst._reduce_summaries", fake_reduce)

    out = rag_analyst_node(
        {"ticker": "AAPL", "company_name": "Apple Inc.", "vectorstore": FakeVectorStore()}
    )

    assert "Apple Inc." in out["risk_factors"]
    assert "Apple Inc." in out["management_guidance"]
