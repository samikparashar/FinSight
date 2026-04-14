import io 
import requests 
from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from config import EMBEDDING_MODEL, RAG_CHUNK_OVERLAP , RAG_CHUNK_SIZE
from state import AgentState

EDGAR_BASE ="https://data.sec.gov"
EDGAR_ARCHIVE = "https://www.sec.gov/Archives/edgar/data"
HEADERS       = {"User-Agent": "FinSight research-bot parasharsamik06@gmail.com"}

#   BASIC FLOW = ticker-> CIK -> latest 10-K filing index -> actual doc url -> raw text -> chunks -> embeddings ->FAISS vectorstore -> return {"vectorstore": ...., "filing_url": ...}

#-------- CIK is central index key (10 digit string) . we need to convert a stock ticker ->CIK 

#************ how data for get_cik looks **********####
# data = {
#   "hits": {
#     "total": {"value": 1},
#     "hits": [
#       {
#         "_index": "search-index",
#         "_type": "_doc",
#         "_id": "some_id",
#         "_source": {
#           "entity_id": 320193,
#           "ticker": "AAPL",
#           "title": "Apple Inc.",
#           "form": "10-K"
#         }
#       }
#     ]
#   }
# }

def _get_cik(ticker :str)->str:
    url  = "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&forms=10-K".format(ticker) #.format(ticker)inserts ticker in {}
    resp = requests.get(url , headers = HEADERS , timeout=15)
    data = resp.json()

    hits = data.get("hits", {}).get("hits",[])
    if not hits:
        raise ValueError(f"No CIK found for ticker: {ticker}")
    
    entity_id = hits[0]["_source"].get("entity_id","")
    cik = str(entity_id).zfill(10)
    print(f"[filingIngestor] CIK for {ticker}: {cik}")
    return cik



#------------- how data looks--------- for the function below 
# data = {
#   "cik": "0000320193",
#   "entityType": "operating",
#   "filings": {
#     "recent": {
#       "accessionNumber": [
#         "0000320193-23-000010",
#         "0000320193-23-000011"
#       ],
#       "filingDate": [
#         "2023-10-27",
#         "2023-07-28"
#       ],
#       "form": [
#         "10-K",
#         "10-Q"
#       ],
#       "primaryDocument": [
#         "aapl-20230930.htm",
#         "aapl-20230630.htm"
#       ]
#     }
#   }
# }

def _get_latest_10k_url(cik:str)->str:
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp=requests.get(url, headers=HEADERS, timeout=15)
    data = resp.json()

    recent = data.get("filings", {}).get("recent",{})
    forms = recent.get("form",  [])
    accnums = recent.get("accessionNumber",[]) #accessionNumber 
    dates = recent.get("filingDate",[])

    for i, form in enumerate(forms):
        if form =="10-K":
            acc_clean = accnums[i].replace("-","")
            filing_date = dates[i] if i<len(dates) else "unknown"
            index_url=(
                 f"{EDGAR_ARCHIVE}/{int(cik)}/{acc_clean}/"
                f"{accnums[i]}-index.json"
            )
            print(f"[FilingIngestor] Found 10-K filed {filing_date}")
            print(f"[FilingIngestor] Index URL: {index_url}")
            return index_url

    raise ValueError(f"No 10-K found for CIK {cik}")


def _get_document_url(index_url: str, cik: str) -> str:
    resp = requests.get(index_url, headers=HEADERS, timeout=15)
    data = resp.json()

    documents = data.get("documents", [])
#------- example for documents structure -----------
# documents = [
#   {"type": "10-K", "name": "aapl-20230930.htm"},
#   {"type": "EX-99", "name": "exhibit.pdf"}
# ]

    for doc in documents:
        doc_type = doc.get("type", "").upper()
        doc_name = doc.get("name", "").lower()

        if doc_type == "10-K" and (
            doc_name.endswith(".htm") or
            doc_name.endswith(".html") or
            doc_name.endswith(".pdf")
        ):
            base = index_url.rsplit("/", 1)[0]
            full_url = f"{base}/{doc['name']}"
            print(f"[FilingIngestor] Document URL: {full_url}")
            return full_url

    for doc in documents:
        if doc.get("name", "").lower().endswith(".pdf"):
            base = index_url.rsplit("/", 1)[0] # Splits the string from the right side Splits only once (1) Uses / as separatorTakes the first part [0] → everything before the last /
            return f"{base}/{doc['name']}"

    raise ValueError("Could not find a valid 10-K document in the filing index")


#------------> till here we have build the url for the latest 10-K file doc url 


def _extract_text_from_url(doc_url: str) -> str:
    print(f"[FilingIngestor] Downloading document...")
    resp = requests.get(doc_url, headers=HEADERS, timeout=60)
    content_type = resp.headers.get("Content-Type", "")
# if out files are in pdf format then we will use this block
    if "pdf" in content_type or doc_url.lower().endswith(".pdf"):
        reader   = PdfReader(io.BytesIO(resp.content))
        raw_text = ""
        for page in reader.pages:
            raw_text += page.extract_text() + "\n"
        print(f"[FilingIngestor] Extracted {len(raw_text):,} chars from PDF")
        return raw_text
    else:
        #if our files are in html format
        from html.parser import HTMLParser

        class _StripHTML(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
            def handle_data(self, data):
                stripped = data.strip()
                if stripped:
                    self.parts.append(stripped)

        parser = _StripHTML()
        parser.feed(resp.text)
        raw_text = "\n".join(parser.parts)
        print(f"[FilingIngestor] Extracted {len(raw_text):,} chars from HTML")
        return raw_text

#---- the most imp function -------
def filing_ingestor_node(state: AgentState) -> dict:

    ticker = state["ticker"]
    print(f"\n[FilingIngestor] Starting SEC filing pipeline for {ticker}...")

    try:
        cik       = _get_cik(ticker)
        index_url = _get_latest_10k_url(cik)
        doc_url   = _get_document_url(index_url, cik)
        raw_text  = _extract_text_from_url(doc_url)

        if len(raw_text) < 500:
            raise ValueError("Extracted text is too short — document may be malformed")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size    = RAG_CHUNK_SIZE,
            chunk_overlap = RAG_CHUNK_OVERLAP,
            separators    = ["\n\n", "\n", ". ", " ", ""],
        )

# each chunk becomees a document  having text and metadatas in json format

        chunks = splitter.create_documents(
            texts    = [raw_text],
            metadatas= [{"ticker": ticker, "source": doc_url}],
        )

        print(f"[FilingIngestor] Created {len(chunks)} text chunks")

        embeddings   = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        vectorstore  = FAISS.from_documents(chunks, embeddings)

        print(f"[FilingIngestor] FAISS index ready with {len(chunks)} vectors")

        return {
            "vectorstore": vectorstore,
            "filing_url" : doc_url,
        }

    except Exception as e:
        print(f"[FilingIngestor] ERROR: {e}")

        return {
            "vectorstore": None,
            "filing_url" : f"Error: {str(e)}",
        }
