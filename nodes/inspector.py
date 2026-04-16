from langchain_groq import ChatGroq
from langchain.messages import HumanMessage , SystemMessage

from config import FAST_MODEL , MAX_SEARCH_ATTEMPTS
from state import AgentState

_llm = ChatGroq(model=FAST_MODEL , temperature=0 )

def inspector_node(state: AgentState)->dict:
    print(f"\n[Inspector] is Validating gathering evidence")

    headlines = state.get("news_headlines",     [])
    financial_data =state.get("financial_data" , "")
    risk_factors = state.get("risk_factors", "")
    guidance = state.get("management_guidance", "")
    search_attempts= state.get("search_attempts" , 0)


    if search_attempts>=MAX_SEARCH_ATTEMPTS:
        print("[Inspector] Max retries reached — forcing pass")

        return{
            "inspector_passed":True,
            "inspector_feedback": ( f"Forced pass after {search_attempts} search attempts. ""Report will proceed with available data."),
        }
    
    if len(headlines)<2:
        msg = f"Only {len(headlines)} headline(s) found — minimum is 2. Will retry search."
        print(f"[Inspector] FAIL — {msg}")
        return {
            "inspector_passed"  : False,
            "inspector_feedback": msg,
        }
    
    data_summary = (
        f"FINANCIAL DATA SAMPLE:\n{financial_data[:400]}\n\n"
        f"NEWS HEADLINES ({len(headlines)} total):\n"
        + "\n".join(headlines[:4])
        + f"\n\nRISK FACTORS EXCERPT:\n{risk_factors[:300]}"
        + f"\n\nGUIDANCE EXCERPT:\n{guidance[:300]}"
    )

    system = "You are a rigorous financial research quality controller."
    user   = (
        f"Evaluate whether the following research data is sufficient to write "
        f"a balanced equity research note.\n\n"
        f"{data_summary}\n\n"
        "Check these criteria:\n"
        "1. BULL_DATA: Is there at least one specific positive data point (growth, strength)?\n"
        "2. BEAR_DATA: Is there at least one specific risk or concern?\n"
        "3. NUMBERS_OK: Does the financial data contain actual numbers (not all N/A)?\n\n"
        "Respond ONLY in this exact format, nothing else:\n"
        "BULL_DATA: yes/no\n"
        "BEAR_DATA: yes/no\n"
        "NUMBERS_OK: yes/no\n"
        "VERDICT: pass/fail\n"
        "REASON: one sentence"
    )

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]

    response=_llm.invoke(messages)
    result = response.content.strip()

    print(f"[Inspector] LLM verdict:\n{result}")

    passed = "VERDICT: pass" in result.lower()

    return {
        "inspector_passed"  : passed,
        "inspector_feedback": result,
    }
