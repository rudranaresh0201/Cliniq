import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

#RAG SETTINGS
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.85))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 5))
MAX_RETRY_LOOPS = int(os.getenv("MAX_RETRY_LOOPS", 3))

#MODELS
GROQ_MODEL = "llama-3.3-70b-versatile"
EMBEDDING_MODEL = "pritamdeka/PubMedBERT-mnli-snli-scinli-scitail-mednli-stsb"

#CHROMADB
CHROMA_COLLECTION = "medical_knowledge"
CHROMA_PATH = "./chroma_db"

# TTL Cache (seconds)
TTL_GUIDELINES = 7 * 24 * 60 * 60
TTL_DRUG_ALERTS = 24 * 60 * 60
TTL_PAPERS = 30 * 24 * 60 * 60

# Source Trust Weights
SOURCE_WEIGHTS = {
    "WHO": 10,
    "CDC": 10,
    "PubMed_meta": 9,
    "PubMed": 8,
    "ClinicalTrials": 8,
    "OpenFDA": 9,
    "MedlinePlus": 7
}

# Query Types
QUERY_TYPES = [
    "emergency",
    "drug_interaction",
    "symptoms",
    "outbreak",
    "diagnosis_support",
    "research",
    "general"
]