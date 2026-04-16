from langchain_groq import ChatGroq
from langchain.messages import HumanMessage , SystemMessage

from config import FAST_MODEL , MAX_SEARCH_ATTEMPTS
from state import AgentState

_llm = ChatGroq(model=FAST_MODEL , temperature=0 )

def inspector_node(state: AgentState)->dict:
    print(f"\n[Inspector] is Validating gathering evidence")

    headlines = state.get("news_headlines",     [])
    financial_data =state.get("financial_data")