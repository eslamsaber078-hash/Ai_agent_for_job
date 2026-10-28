"""Application configuration loaded from environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Populate os.environ from a local .env file without overriding real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


DATABASE_URL = _env(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'jobhunter.db').as_posix()}",
)

OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")

# Free alternative provider: Google Gemini. A free API key from Google AI Studio
# (https://aistudio.google.com) makes the AI-written materials work at no cost.
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.8-flash")

# Second free fallback: Groq (https://console.groq.com/keys). OpenAI-compatible
# API, used when Gemini's free daily quota is exhausted.
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "qwen/qwen3.8-27b")

# Optional: unlocks the "Wuzzuf via Google for Jobs" (JSearch) source.
RAPIDAPI_KEY = _env("RAPIDAPI_KEY")

# Optional: unlocks Jooble, a large Egypt aggregator. Free key from
# https://jooble.org/api/about — silent until configured.
JOOBLE_API_KEY = _env("JOOBLE_API_KEY")

# Optional: unlocks Adzuna, an aggregator of Egyptian job boards. Free key pair
# from https://developer.adzuna.com — silent until both are configured.
ADZUNA_APP_ID = _env("ADZUNA_APP_ID")
ADZUNA_APP_KEY = _env("ADZUNA_APP_KEY")

CORS_ORIGINS = [
    o for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o
]

SESSION_COOKIE_SECURE = _env("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
SESSION_MAX_AGE_SECONDS = int(_env("SESSION_MAX_AGE_SECONDS", "604800"))

HOST = _env("HOST", "127.0.0.1")
PORT = int(_env("PORT", "8000"))

MAX_RESUME_SIZE_MB = 5
ALLOWED_RESUME_TYPES = {".pdf", ".txt", ".doc", ".docx", ".md"}
