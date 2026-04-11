# FinSight Node Architecture Analysis

### Node 1 — market_data_node
1. Purpose of the Node
This node is the quantitative foundation of the entire research pipeline. Its job is to convert a raw stock ticker string into a structured, human-readable block of financial metrics before any reasoning or language generation happens. Every downstream node that needs numbers — the Inspector, the Synthesis node, the Writer — reads from what this node produces. Without it, the LLM nodes would have to either hallucinate financial data or receive no quantitative context at all.
2. Inputs from State
It reads only ticker from state. That single string is enough because yfinance handles all the resolution internally — it maps the ticker to the correct exchange, fetches the relevant company JSON from Yahoo Finance's backend, and returns a flat dictionary of hundreds of fields. Nothing else from state is needed at this stage because this node runs first.
3. Core Logic (Conceptual)
The node thinks like a data normalization layer. It pulls a raw, inconsistently populated dictionary from Yahoo Finance (where any field could be None, 0, or missing entirely) and converts it into a clean, formatted text block. The formatting logic — converting raw floats like 0.1243 into 12.43%, or 3000000000000 into $3.00T — exists because LLMs reason better over human-readable strings than raw numeric values. The node groups metrics into five semantic categories (overview, valuation, growth, balance sheet, dividends) so the downstream LLM nodes can orient themselves quickly when they scan the financial data string.
4. Output to State
Returns four fields: company_name, sector, market_cap, and financial_data. The first three are structured Python values used for string interpolation in prompts. The last — financial_data — is a pre-formatted multi-line string that gets injected verbatim into LLM prompts. This is a deliberate design: by formatting once here, every downstream node gets a consistent, token-efficient representation rather than each node independently formatting the same raw dict.
5. Role in the Full Workflow
This is the entry point of the real work. It runs immediately after the graph receives the initial state (which contains only ticker). LangGraph then fans out from this node to both search_node and filing_ingestor_node in parallel. Both of those downstream nodes depend on company_name and sector from this node's output to form their queries correctly.
6. Design Pattern Used
Data enrichment with normalization. The pattern is: receive a sparse, raw identifier → call an external API → normalize and format the response → write a structured artifact to state for downstream consumption. This is the standard "source of truth" node pattern in data pipelines.
7. Potential Improvements
The biggest risk is yfinance's unofficial API status — Yahoo can break it without notice, and there's no retry or fallback here. A production version should wrap the yf.Ticker call in a retry decorator with exponential backoff, and add a fallback to a secondary data source (Polygon.io or Alpha Vantage) if Yahoo fails. Additionally, the node currently returns market_cap: 0 silently when the field is missing — this should instead set a flag in state like data_quality_warning: True so downstream nodes can calibrate their confidence accordingly.

### Node 2 — search_node
1. Purpose of the Node
This node grounds the research note in current reality. SEC filings are backward-looking (the most recent 10-K could be 11 months old), and Yahoo Finance metrics lag actual business conditions. The search node bridges this gap by fetching recent news, analyst commentary, and market sentiment from the live web. It answers the question: "What has the world said about this company recently that wouldn't appear in historical financial statements?"
2. Inputs from State
It reads ticker, company_name, sector, and search_attempts. The first two are used to construct targeted search queries. sector is used as a fallback query ingredient when primary searches fail. search_attempts is the critical control variable — it determines which of three progressively broader query strategies to use, and it acts as the loop counter that prevents infinite retries when the Inspector sends the agent back.
3. Core Logic (Conceptual)
The node implements a degrading query strategy. On the first attempt, it runs the most specific possible query — company name, ticker, and financial keywords for the current year. If the Inspector rejects the results and routes back here, it runs a broader operational query on the second attempt. On the third attempt, it falls back to sector-level queries. This degradation is intentional: rather than failing hard when a small-cap company has limited coverage, the agent gracefully finds at least some relevant context. The Tavily client's search_depth="advanced" flag triggers deeper crawling of financial sites specifically. The relevance score filter (score > 0.3) prevents low-quality results from contaminating the state.
4. Output to State
Returns news_headlines (a list of formatted strings containing headline, snippet, and source URL), search_query_used (for debugging and audit), and search_attempts (incremented by one). The headlines list is formatted as structured text rather than raw JSON so it can be injected directly into LLM prompts without further transformation.
5. Role in the Full Workflow
This node runs in parallel with filing_ingestor_node after market_data_node completes. Both feed into inspector_node. Uniquely, this node can be visited multiple times — it's the only node in the graph with a possible return edge from the Inspector. This makes it the central node of the self-correction loop.
6. Design Pattern Used
Adaptive retry with query mutation. This is more sophisticated than simple retry — each retry uses a meaningfully different query, not the same query repeated. This pattern recognizes that if a query failed to return good results, repeating it will return the same bad results. The mutation strategy (specific → operational → sector-level) maximizes the chance of finding useful content across retries.
7. Potential Improvements
The node currently has no deduplication across retry attempts — if the same article appears in both attempt #1 and attempt #2, it gets added to news_headlines twice. The state should accumulate unique headlines across retries rather than replacing them. Also, the node should track which sources were already searched and explicitly exclude them in retry queries. A production version would also implement source quality scoring — a Reuters article should be weighted higher than a random blog post.

### Node 3 — filing_ingestor_node
1. Purpose of the Node
This node is the long-document ingestion engine. Its purpose is to convert a 200-page legal PDF from the SEC into a queryable semantic index that the RAG Analyst can search in milliseconds. It's needed because 10-K filings contain the most legally authoritative, candid disclosures a company makes — risk factors, litigation, management discussion — but they're far too long to feed directly to an LLM. This node solves the size problem by converting the document into a vector database.
2. Inputs from State
It reads only ticker from state. Everything else — the CIK number, filing URL, document content — is fetched from external sources (SEC EDGAR) within the node itself. The node is self-contained in its data acquisition because EDGAR lookup is a pure function of the ticker.
3. Core Logic (Conceptual)
The node operates as a four-stage pipeline within a single node: CIK resolution → filing discovery → document download → vector indexing. CIK resolution converts a ticker to SEC's internal company identifier. Filing discovery navigates EDGAR's JSON metadata to find the most recent 10-K accession number and then the actual document URL within that filing's index. Document download handles both PDF and HTML formats with different parsing strategies. Vector indexing is the most computationally significant step — the text is split into overlapping chunks, each chunk is converted to a 1,536-dimensional semantic vector by OpenAI's embedding model, and all vectors are stored in a FAISS index for fast similarity search later.
The chunk overlap is a deliberate design choice: because important sentences can span chunk boundaries, a 200-character overlap ensures no piece of meaning is lost at the edge of a chunk.
4. Output to State
Returns two fields: vectorstore (the FAISS index object, held in memory) and filing_url (the source URL for audit and citation). The vectorstore is the most unusual state field — it's not serializable text, it's a live Python object. This works in the in-process LangGraph execution model but would need to be replaced with a persistent vector DB (Pinecone, Weaviate) in a production distributed system.
5. Role in the Full Workflow
Runs in parallel with search_node after market_data_node. Its output feeds exclusively into rag_analyst_node. If this node fails (EDGAR is down, the document format is unsupported, the ticker has no filings), it returns vectorstore: None and a descriptive error string — a graceful degradation that allows the pipeline to continue without SEC data rather than crashing entirely.
6. Design Pattern Used
Extract-Transform-Load (ETL) with graceful degradation. The try/except wrapper around the entire pipeline means the node never crashes the graph — failure produces a null vectorstore and an error message in state, which the RAG Analyst handles downstream. This is the correct production pattern: a node's failure should degrade the output quality, not halt the entire system.
7. Potential Improvements
The most serious issue is that this node downloads and processes the filing synchronously on every run — for a large 10-K, this can take 30-60 seconds. A production system would cache the vectorstore by (ticker, filing_date) in a persistent vector database and only re-index when a new filing is detected. Additionally, the HTML parser used here is a minimal custom implementation — BeautifulSoup4 would be significantly more robust for handling malformed HTML. The node also doesn't handle multi-document filings where the 10-K is split across multiple exhibit files.

### Node 4 — rag_analyst_node
1. Purpose of the Node
This node is the semantic extraction specialist. Its purpose is to query the FAISS vectorstore with targeted financial questions and synthesize the retrieved chunks into structured analytical content — specifically, risk factors and management guidance. It's needed because the vectorstore contains raw document chunks with no inherent structure; this node imposes analytical structure by asking the right questions and synthesizing the answers.
2. Inputs from State
It reads vectorstore, ticker, and company_name. The vectorstore is the primary input — without it, the node short-circuits entirely. The company name is used in every LLM prompt for context grounding, ensuring the extraction LLM knows which company's filing it's reading (preventing it from generalizing across companies it may have seen in training).
3. Core Logic (Conceptual)
The node implements a Map-Reduce pattern over semantic search results. The Map phase runs six different search queries against the vectorstore — three targeting risk language and three targeting forward guidance language. Using multiple queries is deliberate: a single query like "risk factors" would retrieve chunks using that exact phrase, but important risks might be described as "uncertainties," "threats," or "challenges" in the actual document. Multiple queries with varied vocabulary maximize recall. The Map phase then asks a small LLM to extract only the relevant content from each chunk independently. The Reduce phase takes those mini-extractions and asks the LLM to synthesize them into a coherent 150-200 word analysis with at least one direct quote as evidence. The quote requirement is the anti-hallucination mechanism — it forces the output to contain verifiable text from the source document.
4. Output to State
Returns risk_factors and management_guidance — both are synthesized text strings ready for direct injection into the Synthesis and Writer node prompts. The content has already been through two LLM passes (map + reduce), so it's structured, coherent, and grounded in the source document.
5. Role in the Full Workflow
Sits between filing_ingestor_node and inspector_node. Its outputs are one of the three main evidence streams (alongside financial metrics and news headlines) that the Inspector evaluates. If the vectorstore is None, this node returns placeholder strings and passes control forward — it never blocks the pipeline.
6. Design Pattern Used
Map-Reduce with semantic retrieval. This is the canonical pattern for extracting structured information from long documents without exceeding LLM context limits. The Map step parallelizes the extraction work (each chunk processed independently), and the Reduce step synthesizes the parallel outputs into a coherent whole. The multi-query retrieval strategy is a form of query expansion — a standard RAG improvement technique.
7. Potential Improvements
The Map step currently processes chunks sequentially, which is slow for large filings. Production systems would use asyncio.gather() to parallelize the LLM calls across chunks, potentially 5-10x faster. The deduplication is done by comparing only the first 100 characters of each chunk — this is fragile and would miss near-duplicate chunks with slightly different beginnings. A proper deduplication would use embedding similarity between chunks. Additionally, the node has no mechanism to weight chunks by their position in the document — the risk factors section in a 10-K always appears in a specific location, and a production RAG system would use document structure metadata (section headers) to bias retrieval.

### Node 5 — inspector_node
1. Purpose of the Node
This node is the quality gate and self-correction trigger of the entire system. Its purpose is to answer one question before any reasoning or writing happens: "Is the gathered evidence sufficient to produce a credible, grounded research note?" It's needed because without it, the system would silently produce confident-sounding reports based on thin or missing evidence — the exact hallucination failure mode that makes LLM systems dangerous in financial contexts.
2. Inputs from State
It reads news_headlines, financial_data, risk_factors, management_guidance, and search_attempts. The headlines and financial data are the primary quality signals. The search_attempts counter is the termination condition — the Inspector must check this first, before any other logic, to prevent infinite loops when data is genuinely unavailable.
3. Core Logic (Conceptual)
The node uses a two-tier validation strategy. The first tier is deterministic: a hard check on the number of headlines. This is a cheap, fast rule that catches the most obvious failure case (zero or one result) without calling the LLM. The second tier is probabilistic: an LLM-as-judge call that evaluates whether the content contains both bullish and bearish evidence and whether the financial data has actual numbers. The LLM judge is prompted with a rigid output format (VERDICT: pass/fail) to make parsing reliable. The two-tier approach is efficient — the cheap deterministic check eliminates obvious failures before spending tokens on LLM evaluation.
4. Output to State
Returns inspector_passed (boolean) and inspector_feedback (the LLM's structured evaluation or the deterministic failure reason). The boolean drives the conditional routing function in the graph. The feedback string is passed forward to the Synthesis node, where the LLM Portfolio Manager can see what quality caveats exist about the data.
5. Role in the Full Workflow
This is the only conditional branching node in the system. It sits after both search_node and rag_analyst_node, receives their combined outputs, and makes the binary decision that determines the execution path: forward to Synthesis, or back to Search. This makes it architecturally the most important node — it's the node that makes FinSight an agent rather than a pipeline.
6. Design Pattern Used
Circuit breaker + LLM-as-judge. The MAX_SEARCH_ATTEMPTS check is a classic circuit breaker pattern — it prevents cascading failure by enforcing a hard execution limit. The LLM-as-judge is a modern agentic pattern for non-deterministic quality evaluation where rule-based checks are insufficient. Together they form a defense-in-depth quality gate.
7. Potential Improvements
The LLM judge prompt asks for VERDICT: pass/fail but the parser uses "VERDICT: pass" in result.lower() — this will incorrectly parse "VERDICT: pass (with caveats)" as a pass even if the LLM hedges. The parser should require an exact match. More critically, the Inspector evaluates the search results but has no visibility into the financial data quality level — a ticker where all metrics are N/A should fail the Inspector even if the headlines are plentiful. The NUMBERS_OK check addresses this partially but doesn't cascade into the retry logic (the node can't tell the search node to fix the financial data, because that comes from a different node). In a mature system, the Inspector would have separate retry paths for each evidence stream.

### Node 6 — synthesis_node
1. Purpose of the Node
This node is the analytical reasoning engine — the closest thing in the system to actual investment thinking. Its purpose is to weigh all gathered evidence (quantitative metrics, news sentiment, legal disclosures, management guidance) and construct two opposing structured arguments: the bull case and the bear case. It's needed because raw data doesn't automatically become investment insight — a reasoning step must identify which facts support ownership, which facts warn against it, and why each argument is mechanistically valid.
2. Inputs from State
It consumes every evidence stream: financial_data, news_headlines, risk_factors, management_guidance, and inspector_feedback. The Inspector's feedback is particularly important — it tells the Portfolio Manager LLM what the data quality limitations are, so the synthesis can acknowledge uncertainty appropriately rather than projecting false confidence.
3. Core Logic (Conceptual)
The node uses role prompting with evidence constraints. The system prompt constructs a specific professional identity (senior Portfolio Manager, 20 years experience) that activates a behavioral archetype the LLM has learned from financial writing in its training data. The user prompt then applies a critical constraint: "use ONLY the data below — no outside knowledge." This constraint is the anti-hallucination mechanism. The node also specifies minimum evidence requirements in the prompt itself (at least 2 specific numbers in the bull case, at least 2 specific risks in the bear case) — this structures the output so the Writer node receives well-evidenced arguments rather than vague assertions. The temperature of 0.3 allows enough variability for nuanced expression while keeping the reasoning grounded.
4. Output to State
Returns bull_thesis and bear_thesis as separate text strings. The parsing logic splits the LLM response on the BEAR_THESIS: delimiter, with a fallback midpoint split if the LLM ignores the formatting instruction. Both strings are prose arguments of roughly 150-180 words each, ready for direct inclusion in the Writer's prompt.
5. Role in the Full Workflow
This is the penultimate reasoning node, sitting between the Inspector and the Writer. It's the first node to receive all evidence streams simultaneously and the first to perform genuine multi-source synthesis rather than single-source extraction. Its output is consumed exclusively by writer_node.
6. Design Pattern Used
Constrained generation with role prompting. The combination of a specific professional role (which shapes the reasoning style) and explicit evidence constraints (which prevent hallucination) is a standard production pattern for high-stakes LLM generation. The use of gpt-4o specifically here — while cheaper models are used elsewhere — implements model tiering: spend capability budget where reasoning quality matters most.
7. Potential Improvements
The most significant architectural flaw is that the Synthesis node constructs the bull and bear theses simultaneously in one LLM call. This means the LLM might unconsciously balance them even when the evidence strongly favors one side. A production system would generate each thesis independently, potentially with different system prompts that emphasize the respective perspective, then have a third call reconcile them. Additionally, the node has no validation that the returned bull/bear theses actually contain citations — the requirement is in the prompt, but the output isn't checked. The Inspector runs before synthesis but doesn't check synthesis outputs; a post-synthesis inspector step would catch cases where the LLM ignored the evidence-citation requirement.

### Node 7 — writer_node
1. Purpose of the Node
This node is the presentation and formatting layer. Its purpose is to take the structured analytical outputs from all previous nodes and compile them into a single, professionally formatted Markdown research note that matches institutional equity research conventions. It's needed because raw analytical outputs from the synthesis node are not in a publishable format — they lack structure, citations, a clear recommendation, and a professional framing that makes the output credible and readable to its intended audience.
2. Inputs from State
It consumes the entire state: ticker, company_name, sector, financial_data, news_headlines, bull_thesis, bear_thesis, risk_factors, and management_guidance. This is the only node that needs the full state because its job is to assemble everything into one coherent document. The financial_data is used again here (despite having been used in synthesis) because the Writer needs to populate the Key Statistics section independently.
3. Core Logic (Conceptual)
The node operates as a structured templating engine backed by an LLM. The prompt provides an exact document template with section headers, word count targets, and inline citation requirements ([Source: Yahoo Finance], [Source: SEC 10-K]). The LLM's role is not to reason or discover — all reasoning happened in the Synthesis node — but to fill the template with the correct content from the source data, in the correct voice, at the correct length. The temperature=0.4 setting is slightly higher than the Synthesis node to produce varied, natural-sounding prose rather than mechanical repetition of the input text. The "do not use outside knowledge" instruction is repeated from Synthesis because the Writer is the last line of defense against hallucination — if the LLM fabricates a number here, it appears in the final report.
4. Output to State
Returns final_report — a complete Markdown string that is the terminal output of the entire system. This field is what main.py extracts and saves to disk. It's the only node whose output is intended for human consumption rather than further machine processing.
5. Role in the Full Workflow
This is the terminal node, connected to LangGraph's END. It has no outgoing edges except to END, meaning its output is never routed back or used as input to another node. It's the only node that can directly produce the system's final deliverable.
6. Design Pattern Used
Template-constrained generation. By providing an exact template structure in the prompt, the node constrains the LLM's degrees of freedom to formatting and word choice rather than content selection. This dramatically reduces hallucination risk compared to open-ended generation ("write a research note about this company"). The citation format requirements ([Source: X]) implement grounding markers — they force the LLM to attribute each claim to a specific source, making the output auditable.
7. Potential Improvements
The Writer node has no validation step on its own output. In production, a lightweight post-processing step should verify that the output actually contains the required sections (Recommendation, Bull Case, Bear Case, etc.) before saving. If the LLM deviates from the template, the report is malformed and the user gets a confusing output. Additionally, the report saves only as Markdown — production systems would generate PDF output using a template engine (WeasyPrint, ReportLab) so the report looks like an actual institutional research note. The disclaimer text is hardcoded in the prompt, which is fragile — it should be appended programmatically after generation so it can never be accidentally omitted.

### Overall System Architecture

The DAG Structure
FinSight is a Directed Acyclic Graph with one conditional cycle. The graph has a fan-out from market_data_node, parallel execution across two branches, a convergence at inspector_node, a conditional branch that creates the retry loop, and a linear terminal path to output.
[ticker input]
      |
      v
[market_data_node]          ← Entry point. Runs once. Always.
      |
   (fan-out)
    /        \
   v           v
[search_node]   [filing_ingestor_node]   ← Parallel execution
   |                   |
   |            [rag_analyst_node]
   |                   |
   \                  /
    (convergence)
          |
          v
   [inspector_node]          ← The only decision point
          |
    (conditional)
       /       \
      v          v
[synthesis]   [search_node]  ← Retry loop (back to search)
      |
      v
 [writer_node]
      |
     END

### Data Flow Step-by-Step
Stage 1 — Initialization. main.py creates an initial state with three fields: ticker, search_attempts: 0, and inspector_passed: False. LangGraph validates this against the AgentState TypedDict and begins execution.

Stage 2 — Quantitative Foundation. market_data_node runs first and adds company_name, sector, market_cap, and financial_data to state. The graph then fans out to both search_node and filing_ingestor_node simultaneously. LangGraph manages this parallelism internally — both nodes receive a copy of the current state and their return dicts are merged back into state when both complete.

Stage 3 — Evidence Gathering (Parallel). While search_node is calling the Tavily API to fetch news headlines, filing_ingestor_node is independently resolving the CIK, downloading the SEC filing, chunking it, and building the FAISS index. These two operations are fully independent and share no state during execution. When both finish, state contains news_headlines from Search and vectorstore from the ingestor.

Stage 4 — SEC Semantic Extraction. rag_analyst_node runs sequentially after filing_ingestor_node completes. It uses the vectorstore from state to run six targeted similarity searches and produces risk_factors and management_guidance through Map-Reduce summarization.

Stage 5 — Quality Gate. inspector_node runs after both search_node and rag_analyst_node have written their outputs to state. It evaluates the full evidence picture and sets inspector_passed. The conditional routing function then reads this boolean and selects the execution path.

Stage 6A — Retry Path. If inspector_passed is False, the router returns "search" and LangGraph routes execution back to search_node. The search_attempts counter in state has already been incremented, so the search node's degrading query strategy selects a different query. The pipeline then runs: search_node → inspector_node → (decision) again. This loop can execute at most MAX_SEARCH_ATTEMPTS times (3) before the Inspector forces a pass.

Stage 6B — Forward Path. If inspector_passed is True, the router returns "synthesis" and the linear terminal path executes: synthesis_node → writer_node → END.

Stage 7 — Synthesis and Writing. synthesis_node receives the complete evidence state and produces bull_thesis and bear_thesis. writer_node receives the complete state including the theses and produces final_report. LangGraph reaches END and returns the final state to main.py.
Where Decision-Making and Retries Happen
There is exactly one decision point in the system: the conditional edge out of inspector_node. This is deliberate — having multiple decision points would create an exponentially complex execution graph that's hard to reason about and debug. All other nodes are deterministic given their inputs.
The retry mechanism is not a loop in the graph definition — it's a conditional edge that points back to an earlier node. LangGraph handles this at the execution level, not the graph structure level. The graph itself remains a DAG; the cycle exists only in the runtime execution path. The search_attempts counter is the only thing that guarantees termination — remove it, and the graph can loop indefinitely.
Key Architectural Strengths
The system separates concerns cleanly: data acquisition (market data, search, filing), extraction (RAG analyst), validation (inspector), reasoning (synthesis), and presentation (writer) are all independent nodes with no cross-dependencies except through state. This means any node can be replaced or upgraded without touching the others. The graceful degradation pattern — where filing_ingestor_node and search_node both handle failures by writing placeholder values rather than raising exceptions — means the system produces a partial report rather than crashing entirely, which is the correct behavior for a research tool that encounters sparse data on small-cap stocks.

### Key Architectural Weaknesses

The vectorstore is stored as a live Python object in state, which means the system cannot be distributed across multiple processes or serialized for checkpointing — a critical limitation if you want to add human-in-the-loop review steps or resume interrupted runs. The parallel execution of search_node and filing_ingestor_node is implicit in the graph edges rather than explicit with LangGraph's Send() API, which limits control over parallel execution parameters. And there is no post-synthesis quality check — the Writer node's output is never validated, meaning a malformed report can reach the user without detection.
# FinSight Node Architecture — Notes

---

## Node 1 — market_data_node

### Purpose
- Converts ticker → structured financial metrics
- Acts as quantitative foundation

### Inputs
- ticker

### Core Idea
- Fetch raw data (yfinance)
- Normalize + format for LLM readability
- Group into categories (valuation, growth, etc.)

### Output
- company_name
- sector
- market_cap
- financial_data (formatted string)

### Role
- First node
- Feeds search + filing nodes

### Pattern
- Data enrichment + normalization

### Improvements
- Add retry + fallback APIs
- Handle missing data explicitly

---

## Node 2 — search_node

### Purpose
- Fetch latest news + sentiment

### Inputs
- ticker, company_name, sector
- search_attempts

### Core Idea
- Adaptive query strategy:
  - Attempt 1 → precise
  - Attempt 2 → financial
  - Attempt 3 → broad

### Output
- news_headlines
- search_query_used
- search_attempts++

### Role
- Parallel with filing node
- Part of retry loop

### Pattern
- Adaptive retry + query mutation

### Improvements
- Dedup results
- Track sources
- Add quality scoring

---

## Node 3 — filing_ingestor_node

### Purpose
- Convert SEC filing → vector database

### Inputs
- ticker

### Core Idea
- Pipeline:
  - CIK → filing → download → chunk → embed → FAISS

### Output
- vectorstore
- filing_url

### Role
- Feeds RAG analyst

### Pattern
- ETL + graceful degradation

### Improvements
- Cache vectorstore
- Use better HTML parser
- Handle multi-doc filings

---

## Node 4 — rag_analyst_node

### Purpose
- Extract risks + guidance from filings

### Inputs
- vectorstore, ticker, company_name

### Core Idea
- Map-Reduce:
  - Multi-query retrieval
  - Extract → synthesize

### Output
- risk_factors
- management_guidance

### Role
- Feeds inspector

### Pattern
- RAG + Map-Reduce

### Improvements
- Parallelize LLM calls
- Better deduplication
- Use document structure

---

## Node 5 — inspector_node

### Purpose
- Quality gate + retry trigger

### Inputs
- headlines, financials, risks, guidance
- search_attempts

### Core Idea
- 2-stage validation:
  - Rule-based (count check)
  - LLM judge (quality check)

### Output
- inspector_passed
- inspector_feedback

### Role
- Only decision node
- Controls retry loop

### Pattern
- Circuit breaker + LLM judge

### Improvements
- Strict parsing
- Better financial validation
- Multi-path retries

---

## Node 6 — synthesis_node

### Purpose
- Generate bull + bear cases

### Inputs
- all evidence + inspector feedback

### Core Idea
- Role prompting (Portfolio Manager)
- Evidence-constrained reasoning

### Output
- bull_thesis
- bear_thesis

### Role
- Main reasoning step

### Pattern
- Constrained generation

### Improvements
- Separate bull/bear generation
- Add output validation

---

## Node 7 — writer_node

### Purpose
- Generate final report

### Inputs
- full state

### Core Idea
- Template-based generation
- Add citations + structure

### Output
- final_report

### Role
- Final node → END

### Pattern
- Template-constrained generation

### Improvements
- Validate output format
- Add PDF export
- Move disclaimer to code

---

## Overall Architecture

### Flow
```
ticker → market_data
        → (parallel)
           → search
           → filing → rag
        → inspector
            → retry (search)
            → or synthesis
        → writer → END
```

### Key Concepts
- Parallel execution
- Single decision point
- Retry loop via state

### Strengths
- Modular design
- Graceful failure handling
- Clear separation of concerns

### Weaknesses
- In-memory vectorstore
- No final validation
- Limited parallel control

```