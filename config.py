import os 
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SEC_API_KEY = os.getenv("SEC_API_KEY")



# for fast = cheap+low latency (groq)
FAST_MODEL="llama-3.1-8b-instant" 
# FAST_MODEL = "gpt-4o-mini"
FAST_MODEL_API_KEY=GROQ_API_KEY

# Powerful = better reasoning (groq)
POWERFUL_MODEL="openai/gpt-oss-120b"
POWERFUL_MODEL_API_KEY=GROQ_API_KEY

# Local embedding model (no OpenAI dependency)
EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"


# here we are doing RAG CONFIGURATIONS 
MAX_SEARCH_ATTEMPTS = 3 
RAG_CHUNK_SIZE = 1000
RAG_CHUNK_OVERLAP = 200 
RAG_TOP_K =3 
MAX_RAG_CHUNKS = 6 
