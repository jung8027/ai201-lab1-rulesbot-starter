import os
from dotenv import load_dotenv

load_dotenv()

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = "llama-3.3-70b-versatile"

# --- Embeddings ---
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# --- Vector store ---
CHROMA_COLLECTION = "rulesbot"
CHROMA_PATH = "./chroma_db"

# --- Retrieval ---
N_RESULTS = 3

# Maximum cosine distance for a chunk to count as relevant. Chunks above this
# are treated as weak matches and dropped before generation, so the model is
# never asked to answer from off-topic context. ~0.5 is weak for this embedding
# model; 0.75 keeps genuine supporting passages while rejecting clear misses.
RELEVANCE_THRESHOLD = 0.75

# --- Documents ---
DOCS_PATH = "./docs"
