from langgraph.graph import StateGraph, END

from state import AgentState
from nodes.market_data    import market_data_node
from nodes.search         import search_node
from nodes.filing_ingestor import filing_ingestor_node
from nodes.rag_analyst    import rag_analyst_node
from nodes.inspector      import inspector_node
from nodes.synthesis      import synthesis_node
from nodes.writer         import writer_node

# to check if you need to go back in the graph to retry 
def route_after_inspector(state: AgentState) -> str:
    if state.get("inspector_passed", False):
        print("[Router] Inspector PASSED -> Synthesis")
        return "synthesis"
    else:
        print("[Router] Inspector FAILED -> Search (retry)")
        return "search"
    
def build_graph():
    graph = StateGraph(AgentState)
    
