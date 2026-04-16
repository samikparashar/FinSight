import sys 
import os 
from datetime import datetime
from graph import build_graph


def run_finsight(ticker: str):
    print("\n" + "=" * 60)
    print("  FinSight — Autonomous Financial Research Agent")
    print(f"Analysing: {ticker.upper()}")
    print("\n" + "=" * 60)

    app = build_graph()

    initial_state= {
        "ticker"        :ticker.upper(),
        "search_attempts" :0 , 
        "inspector_passed" : False,
    }

    print("\n[Main] Invoking LangGraph state machine...\n")

    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        print(f"\n[Main] Fatal error during graph execution: {e}")
        raise

    report = final_state.get("final_report", "")

    if not report:
        print("[Main] ERROR: No report was generated.")
        return

    print("\n" + "=" * 60)
    print("  RESEARCH NOTE OUTPUT")
    print("=" * 60 + "\n")
    print(report)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir  = "reports"
    os.makedirs(output_dir, exist_ok=True)
    filename    = f"{output_dir}/{ticker.upper()}_{timestamp}.md"
    # filename = os.path.join(output_dir, f"{ticker.upper()}_{timestamp}.md")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n[Main] Report saved to: {filename}")
    print("[Main] Done.\n")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <TICKER>")
        print("Example: python main.py AAPL")
        sys.exit(1)

    ticker = sys.argv[1].strip().upper()
    run_finsight(ticker)