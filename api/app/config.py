from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_model: str
    groq_vision_model: str
    max_upload_mb: int
    top_k: int
    database_path: str
    mongodb_uri: str
    mongodb_database: str

    @property
    def max_upload_bytes(self):
        return self.max_upload_mb * 1024 * 1024

settings = Settings(
    groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
    groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
    groq_vision_model=os.getenv(
        "GROQ_VISION_MODEL", "qwen/qwen3.8-27b"
    ).strip(),
    max_upload_mb=max(1, int(os.getenv("MAX_UPLOAD_MB", "4"))),
    top_k=max(1, min(20, int(os.getenv("TOP_K", "5")))),
    database_path=os.getenv("DATABASE_PATH", "./data/studyrag.db"),
    mongodb_uri=os.getenv("MONGODB_URI", "").strip(),
    mongodb_database=os.getenv("MONGODB_DATABASE", "studyrag").strip(),
)
Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
