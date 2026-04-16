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

    graph.add_node("market_data",     market_data_node)
    graph.add_node("search",          search_node)
    graph.add_node("filing_ingestor", filing_ingestor_node)
    graph.add_node("rag_analyst",     rag_analyst_node)
    graph.add_node("inspector",       inspector_node)
    graph.add_node("synthesis",       synthesis_node)
    graph.add_node("writer",          writer_node)

    graph.set_entry_point("market_data")
    
    graph.add_edge("market_data" ,      "search")
    graph.add_edge("market_data",       "filing_ingestor")
    graph.add_edge("filing_ingestor" ,  "rag_analyst")
    graph.add_edge("rag_analyst",       "inspector")
    graph.add_edge("search",            "inspector")
    graph.add_edge("synthesis",         "writer")
    graph.add_edge("writer",            END)

    graph.add_conditional_edges(
        "inspector",
        route_after_inspector,{ 
            "synthesis": "synthesis",
            "search"   : "search",
        }
    )

    return graph.compile()
