from nodes.filing_ingestor import (
    _get_cik,
    _get_document_url,
    _get_latest_10k_url,
    filing_ingestor_node,
)


class FakeResponse:
    def __init__(self, json_data=None, headers=None, text="", content=b""):
        self._json_data = json_data or {}
        self.headers = headers or {}
        self.text = text
        self.content = content

    def json(self):
        return self._json_data


def test_get_cik_success(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            json_data={
                "hits": {
                    "hits": [
                        {"_source": {"entity_id": 320193}},
                    ]
                }
            }
        )

    monkeypatch.setattr("nodes.filing_ingestor.requests.get", fake_get)

    assert _get_cik("AAPL") == "0000320193"


def test_get_latest_10k_url_success(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            json_data={
                "filings": {
                    "recent": {
                        "form": ["10-Q", "10-K"],
                        "accessionNumber": ["0001-01-000001", "0001-02-000002"],
                        "filingDate": ["2025-10-01", "2025-12-01"],
                    }
                }
            }
        )

    monkeypatch.setattr("nodes.filing_ingestor.requests.get", fake_get)

    out = _get_latest_10k_url("0000000001")
    assert out.endswith("/0001-02-000002-index.json")


def test_get_document_url_prefers_main_10k_doc(monkeypatch):
    def fake_get(url, headers, timeout):
        return FakeResponse(
            json_data={
                "documents": [
                    {"type": "EX-99", "name": "exhibit.pdf"},
                    {"type": "10-K", "name": "main10k.htm"},
                ]
            }
        )

    monkeypatch.setattr("nodes.filing_ingestor.requests.get", fake_get)

    index_url = "https://www.sec.gov/Archives/edgar/data/1/2/0001-index.json"
    out = _get_document_url(index_url, "0000000001")
    assert out.endswith("/main10k.htm")


def test_filing_ingestor_node_returns_graceful_error(monkeypatch):
    def fake_get_cik(_ticker):
        raise ValueError("No CIK found")

    monkeypatch.setattr("nodes.filing_ingestor._get_cik", fake_get_cik)

    out = filing_ingestor_node({"ticker": "XXXX"})
    assert out["vectorstore"] is None
    assert out["filing_url"].startswith("Error:")
