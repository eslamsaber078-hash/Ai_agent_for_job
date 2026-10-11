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

CORS_ORIGINS = [
    o for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o
]

HOST = _env("HOST", "127.0.0.1")
PORT = int(_env("PORT", "8000"))

MAX_RESUME_SIZE_MB = 5
ALLOWED_RESUME_TYPES = {".pdf", ".txt", ".doc", ".docx", ".md"}
