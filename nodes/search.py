# this node fetches the recent news and analyst sentinment via tavily.
# # It also impletemts the retry counter used by the self correction loop .

from tavily import TavilyClient
from config import TAVILY_API_KEY, MAX_SEARCH_ATTEMPTS
from state import AgentState

_client =TavilyClient(api_key=TAVILY_API_KEY)

def search_node(state:AgentState) ->dict :
    ticker = state["ticker"]
    company_name = state.get("company_name",ticker)
    attempts=state.get("search_attempts",0)

    print(f"\n[Search] Attempt #{attempts+1} for {company_name}...")

    if attempts == 0 :
        query =f"{company_name} {ticker} stock earnings analyst rating 2024 2025"
    elif attempts == 1:
        query =f"{company_name} revenue profit quarterly results outlook "
    else :
        sector = state.get("sector","technology")
        query = f"{ticker}{sector} stock market performance investment"
    print(f"[Search] Query: '{query}'")

    try:
        response = _client.search(
            query=query,
            max_result=8,
            search_depth="advanced",
            include_raw_content=False,
            include_answer=True ,
        )
    except Exception as e:
        print(f"[Search] Error: {e}")
        return{
            "news_headlines"        :[f"Search failed: {str(e)}"],
            "search_query_used"     :query,
            "search_attempts"       : attempts+1,
        }
    
    headlines=[]

    if response.get("answer"):
        headlines.append(f"[Summary] {response['answer']}")

    for result in response.get("results",[]):
        title       = result.get("title",    "").strip()
        snippet     = result.get("content",  "").strip()
        url         =result.get("url",  "")
        score       =result.get("score",  0)
        if title and score > 0.3:
            headlines.append(
                f"HEADLINE: {title}\n"
                f"  DETAIL : {snippet}\n"
                f"  SOURCE : {url}"
            )

    print(f"[Search] Retrieved {len(headlines)} headlines")

    return {
        "news_headlines"        :headlines,
        "search_query_used"     :query,
        "search_attempts"       :attempts+1,
    }



    



