
from typing import TypedDict , Optional , List , Any 


class AgentState(TypedDict , total=False):
    ticker: str 

    company_name : str
    sector: str
    market_cap: float

    news_headlines: List[str]
    search_query_used: str
    search_attemps:int
    filing_url: str 
    vectorstore: Any

    risk_factors: str 
    managements_guidance:str

    bull_thesis:str
    bear_thesis:str 

    inspector_passed : bool 
    inspector_feedback:str
    
    final_report:str
