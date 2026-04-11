import yfinance as yf
from state import AgentState

def market_data_node(state :AgentState)->dict:

    ticker=state["ticker"]
    print(f"\n[Market] Fetching data for {ticker}...")

    stock = yf.Ticker(ticker)
    info =stock.info

    company_name = info.get("longName", ticker)
    sector       = info.get("sector" , "unknown")
    market_cap   = info.get("marketCap" , 0) or 0 

    pe_trailing  = info.get("trailingPE",           "N/A")
    pe_forward   = info.get("forwardPE",            "N/A")
    pb_ratio     = info.get("priceToBook",          "N/A")
    ev_ebitda    = info.get("enterpriseToEbitda",   "N/A")

    rev_growth   = info.get("revenueGrowth",        "N/A")
    earn_growth  = info.get("earningsGrowth",       "N/A")
    profit_mgn   = info.get("profitMargins",        "N/A")
    gross_mgn    = info.get("grossMargins",         "N/A")

    debt_equity  = info.get("debtToEquity",         "N/A")
    current_r    = info.get("currentRatio",         "N/A")
    fcf          = info.get("freeCashflow",         "N/A")
    cash         = info.get("totalCash",            "N/A")

    div_yield    = info.get("dividendYield",        "N/A")
    payout       = info.get("payoutRatio",          "N/A")

    beta         = info.get("beta",                 "N/A")
    week_52_high = info.get("fiftyTwoWeekHigh",     "N/A")
    week_52_low  = info.get("fiftyTwoWeekLow",      "N/A")
    curr_price   = info.get("currentPrice",         "N/A")

    def fmt_num(val): # converts to readable like 1000000 to 1M
        if isinstance(val,(int,float)):
            if abs(val)>=1_000_000_000_000:
             return f"${val/1_000_000_000_000:.2f}T"
        
        elif abs(val)>=1_000_000_000:
             return f"${val/1_000_000_000:.2f}B"
        elif abs(val)>=1_000_000:
             return f"${val/1_000_000:.2f}M"
        else:
            return f"${val:.2f}"
        return str(val)

    def fmt_pct(val): # converts to perc 0.45 to 45% 
        if isinstance(val,float):
            return f"{val*100:.2f}%" 
        return str(val)

    financial_data=f"""
    COMPANY OVERVIEW
        Name            : {company_name}
        Ticker          : {ticker}
        Sector          : {sector}
        Market Cap      : {fmt_num(market_cap)}
        Current Price   : {fmt_num(curr_price)}
        52-Week High    : {fmt_num(week_52_high)}
        52-Week Low     : {fmt_num(week_52_low)}
        Beta            : {beta}

    VALUATION METRICS 
    Trailing P/E      : {pe_trailing}
    Forward P/E       : {pe_forward}
    Price/Book        : {pb_ratio}
    EV/EBITDA         : {ev_ebitda}

    GROWTH METRICS
    Revenue Growth (YoY)    : {fmt_pct(rev_growth)}
    Earnings Growth (YoY)   : {fmt_pct(earn_growth)}
    Profit Margin           : {fmt_pct(profit_mgn)}
    Gross Margin            : {fmt_pct(gross_mgn)}

    BALANCE SHEET HEALTH
    Debt / Equity  : {debt_equity}
    Current Ratio  : {current_r}
    Free Cash Flow : {fmt_num(fcf)}
    Total Cash     : {fmt_num(cash)}

    DIVIDEND INFO
    Dividend Yield : {fmt_pct(div_yield)}
    Payout Ratio   : {fmt_pct(payout)}
""".strip()
    
    print(f"[MarketData] Done — {company_name}, Market Cap: {fmt_num(market_cap)}")

    return {
        "company_name" : company_name,
        "sector"       : sector,
        "market_cap"   : market_cap,
        "financial_data": financial_data,
    }

        