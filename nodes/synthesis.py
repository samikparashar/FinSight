from langchain_groq import ChatGroq
from langchain.messages import HumanMessage , SystemMessage

from config import POWERFUL_MODEL
from state import AgentState

_llm = ChatGroq(model=POWERFUL_MODEL, temperature=0.3)

_SYSTEM = """
You are a senior Portfolio Manager at a premier investment bank with 20 years
of equity research experience across technology, consumer, and industrial sectors.

Your principles:
- Ground every claim in the data provided — no fabrication
- Acknowledge what you don't know or what the data doesn't show
- Distinguish between historical fact and forward-looking inference
- A good thesis names the specific mechanism by which value is created or destroyed
- Use exact numbers and quotes from the source material as evidence
"""


def synthesis_node(state: AgentState) -> dict:

    ticker       = state["ticker"]
    company_name = state.get("company_name", ticker)

    print(f"\n[Synthesis] Portfolio Manager analyzing {company_name}...")

    headlines_text = "\n".join(state.get("news_headlines", [])[:6])

    user = f"""
Analyze {company_name} ({ticker}) using ONLY the data below.

=== FINANCIAL METRICS ===
{state.get("financial_data", "Not available")}

=== RECENT NEWS & ANALYST COMMENTARY ===
{headlines_text if headlines_text else "No news available"}

=== SEC FILING — RISK FACTORS ===
{state.get("risk_factors", "Not available")}

=== SEC FILING — MANAGEMENT GUIDANCE ===
{state.get("management_guidance", "Not available")}

=== DATA QUALITY NOTES ===
{state.get("inspector_feedback", "No notes")}

---
Based ONLY on the above, write the following. Do not use any outside knowledge.

BULL_THESIS:
Write 150-180 words making the strongest possible case for the stock.
Requirements:
- Cite at least 2 specific numbers from the financial metrics section
- Reference at least 1 piece of management guidance
- Name the core mechanism driving value creation

BEAR_THESIS:
Write 150-180 words making the strongest possible case against the stock.
Requirements:
- Cite at least 2 specific risks from the SEC filing
- Acknowledge at least 1 specific metric that is concerning or missing
- Name the core mechanism that could destroy value
"""

    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=user),
    ]

    response = _llm.invoke(messages)
    content  = response.content.strip()

    bull_thesis = ""
    bear_thesis = ""

    if "BULL_THESIS:" in content and "BEAR_THESIS:" in content:
        parts = content.split("BEAR_THESIS:")
        bull_thesis = parts[0].replace("BULL_THESIS:", "").strip()
        bear_thesis = parts[1].strip()
    else:
        mid = len(content) // 2
        bull_thesis = content[:mid].strip()
        bear_thesis = content[mid:].strip()

    print(f"[Synthesis] Bull thesis: {len(bull_thesis)} chars")
    print(f"[Synthesis] Bear thesis: {len(bear_thesis)} chars")

    return {
        "bull_thesis": bull_thesis,
        "bear_thesis": bear_thesis,
    }