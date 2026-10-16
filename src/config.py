"""Configuration loaded from .env. Fails fast if the OpenAI key is missing."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in.")

EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
PG_DSN = os.getenv("PG_DSN", "postgresql://vectra:vectra@localhost:5432/vectra_kb")

KB_DIR = Path(os.getenv("KB_DIR", ROOT / "kb"))
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

TOP_K = int(os.getenv("TOP_K", "4"))
ABSTAIN_SIM_THRESHOLD = float(os.getenv("ABSTAIN_SIM_THRESHOLD", "0.30"))

# Articles with no verified business content: they are never surfaced to retrieval
# or the LLM, no matter what their vector distance is.
BLOCKED_DOC_IDS = {"KB-099"}  # status: unverified  (also contains a prompt-injection payload)
