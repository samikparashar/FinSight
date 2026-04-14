# we use map reduce here 
from langchain_groq import ChatGroq
from langchain.messages import HumanMessage , SystemMessage

from config import FAST_MODEL , RAG_TOP_K , MAX_RAG_CHUNKS
from state import AgentState

llm = ChatGroq(model=FAST_MODEL , temperature=0) # Temperature controls randomness in model output. for 0.0-0.3 more focused and consistent (RAG systems , factual ans , code generation )
#for 0.5-0.7 balanced creativity +accuracy , slight variation in responses , summaries ,chat assistants 
# 0.8-0.12 more random and creative , less predictable for storytelling , brainstorming , idea generation 
# Temperature = “creativity knob”

RISK_QUERIES = [
    "risk factors business risks competitive threats regulatory",
    "litigation legal proceedings material risks uncertainty ",
    "market risks foreign currency interest rate exposure",
]
GUIDANCE_QUERIES = [
    "management outlook guidance forward looking revenue forecast",
    "CEO strategic priorities growth initiatives next year",
    "operating guidance capital expenditure investment plans",
]
def _call_llm(system_msg :str , user_msg:str)->str:
    messages=[
        SystemMessage(content=system_msg),
        HumanMessage(content = user_msg),
    ]
    response = llm.invoke(messages)
    return response.content.strip()

def _map_chunks(chunks: list , task_description : str , company : str)->list:
    summaries= []
    for chunk in chunks[:MAX_RAG_CHUNKS]:
        system = "You are a financial analyst. Be concise and extract only what is relevant."
        user   = (
            f"Company: {company}\n"
            f"Task: {task_description}\n\n"
            f"Document excerpt:\n{chunk.page_content}\n\n"
            "In 2-3 sentences, extract the most relevant information. "
            "If the excerpt is clearly not relevant, reply exactly: NOT_RELEVANT"
        )
        result = _call_llm(system, user)
        if "NOT_RELEVANT" not in result:
            summaries.append(result)
    return summaries


def _reduce_summaries(summaries: list, task_description: str, company: str) -> str:
    if not summaries:
        return "No relevant information found in the SEC filing."

    combined = "\n\n".join(
        f"[Excerpt {i+1}]:\n{s}" for i, s in enumerate(summaries)
    )

    system = (
        "You are a senior equity analyst synthesizing SEC filing disclosures. "
        "Be precise, cite specifics, and include at least one direct quote in quotation marks."
    )
    user = (
        f"Company: {company}\n"
        f"Task: {task_description}\n\n"
        f"Here are extractions from multiple parts of the SEC filing:\n\n{combined}\n\n"
        "Synthesize these into a single, coherent 150-200 word analysis. "
        "Include at least one direct quote from the material as evidence."
    )
    return _call_llm(system, user)

## NODE 
def rag_analyst_node(state: AgentState) -> dict:

    vectorstore  = state.get("vectorstore")
    ticker       = state["ticker"]
    company_name = state.get("company_name", ticker)

    print(f"\n[RAGAnalyst] Semantic search over {company_name} 10-K...")

    if vectorstore is None:
        print("[RAGAnalyst] No vectorstore — skipping RAG")
        return {
            "risk_factors"       : "SEC filing data unavailable for this ticker.",
            "management_guidance": "SEC filing data unavailable for this ticker.",
        }

    risk_chunks = []
    for q in RISK_QUERIES:
        docs = vectorstore.similarity_search(q, k=RAG_TOP_K)
        risk_chunks.extend(docs)

    seen = set()
    unique_risk = []
    for doc in risk_chunks:
        key = doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            unique_risk.append(doc)

    guidance_chunks = []
    for q in GUIDANCE_QUERIES:
        docs = vectorstore.similarity_search(q, k=RAG_TOP_K)
        guidance_chunks.extend(docs)

    seen = set()
    unique_guidance = []
    for doc in guidance_chunks:
        key = doc.page_content[:100]
        if key not in seen:
            seen.add(key)
            unique_guidance.append(doc)

    print(f"[RAGAnalyst] Retrieved {len(unique_risk)} risk chunks, "
          f"{len(unique_guidance)} guidance chunks")

    risk_task     = "Extract the 3 most significant risk factors disclosed by the company."
    guidance_task = "Extract management's specific forward-looking guidance, targets, and strategic priorities."

    risk_summaries     = _map_chunks(unique_risk,     risk_task,     company_name)
    guidance_summaries = _map_chunks(unique_guidance, guidance_task, company_name)

    risk_factors        = _reduce_summaries(risk_summaries,     risk_task,     company_name)
    management_guidance = _reduce_summaries(guidance_summaries, guidance_task, company_name)

    print(f"[RAGAnalyst] Risk factors: {len(risk_factors)} chars")
    print(f"[RAGAnalyst] Guidance    : {len(management_guidance)} chars")

    return {
        "risk_factors"       : risk_factors,
        "management_guidance": management_guidance,
    }
