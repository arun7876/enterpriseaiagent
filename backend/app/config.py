import os
import secrets
import sys
import logging
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _path_setting(name: str, default: Path) -> Path:
    value = os.getenv(name)
    path = Path(value).expanduser() if value else default
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _bool_setting(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    jwt_secret: str
    jwt_cookie_secure: bool
    allow_self_service_registration: bool
    access_token_ttl_minutes: int
    cors_allowed_origins: tuple[str, ...]
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    embedding_model: str
    hf_home: Path
    data_dir: Path
    auth_db_path: Path
    document_catalog_path: Path
    upload_dir: Path
    rag_index_path: Path
    business_db_path: Path
    max_upload_size_bytes: int
    rag_min_relevance_score: float
    log_level: str

    def validate(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise RuntimeError("APP_ENV must be development, test, or production.")
        if not self.cors_allowed_origins:
            raise RuntimeError("CORS_ALLOWED_ORIGINS must contain at least one origin.")
        if self.max_upload_size_bytes <= 0:
            raise RuntimeError("MAX_UPLOAD_SIZE_BYTES must be greater than zero.")
        if not 1 <= self.access_token_ttl_minutes <= 1440:
            raise RuntimeError("ACCESS_TOKEN_TTL_MINUTES must be between 1 and 1440.")
        if self.ollama_timeout_seconds <= 0:
            raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be greater than zero.")
        if not 0 <= self.rag_min_relevance_score <= 1:
            raise RuntimeError("RAG_MIN_RELEVANCE_SCORE must be between 0 and 1.")
        if not isinstance(logging.getLevelName(self.log_level), int):
            raise RuntimeError("LOG_LEVEL must be a valid Python logging level.")
        if self.app_env == "production":
            if self.allow_self_service_registration:
                raise RuntimeError("ALLOW_SELF_SERVICE_REGISTRATION must be disabled in production.")
            secret = self.jwt_secret.lower()
            if len(self.jwt_secret) < 32 or len(set(self.jwt_secret)) < 12 or any(
                marker in secret
                for marker in ("replace-me", "replace-with", "change-me", "placeholder")
            ):
                raise RuntimeError("JWT_SECRET must be a generated secret of at least 32 characters in production.")
            if not self.jwt_cookie_secure:
                raise RuntimeError("JWT_COOKIE_SECURE must be enabled in production.")
            if not os.getenv("CORS_ALLOWED_ORIGINS") or any(
                not origin.startswith("https://") for origin in self.cors_allowed_origins
            ):
                raise RuntimeError("Production CORS_ALLOWED_ORIGINS must explicitly list HTTPS origins.")


def _load_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    configured_secret = os.getenv("JWT_SECRET", "").strip()
    if configured_secret:
        jwt_secret = configured_secret
    elif environment == "production":
        jwt_secret = ""
    else:
        jwt_secret = secrets.token_urlsafe(48)

    data_dir = _path_setting("DATA_DIR", PROJECT_ROOT / "data")
    settings = Settings(
        app_env=environment,
        jwt_secret=jwt_secret,
        jwt_cookie_secure=_bool_setting("JWT_COOKIE_SECURE", environment == "production"),
        allow_self_service_registration=_bool_setting(
            "ALLOW_SELF_SERVICE_REGISTRATION", environment != "production"
        ),
        access_token_ttl_minutes=int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60")),
        cors_allowed_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
            ).split(",")
            if origin.strip()
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        hf_home=_path_setting("HF_HOME", data_dir / "models" / "huggingface"),
        data_dir=data_dir,
        auth_db_path=_path_setting("AUTH_DB_PATH", data_dir / "auth.sqlite3"),
        document_catalog_path=_path_setting("DOCUMENT_CATALOG_PATH", data_dir / "documents.sqlite3"),
        upload_dir=_path_setting("UPLOAD_DIR", data_dir / "uploads"),
        rag_index_path=_path_setting("RAG_INDEX_PATH", data_dir / "index" / "vector_index.sqlite3"),
        business_db_path=_path_setting("BUSINESS_DB_PATH", data_dir / "business_analytics.sqlite3"),
        max_upload_size_bytes=int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024))),
        rag_min_relevance_score=float(os.getenv("RAG_MIN_RELEVANCE_SCORE", "0.30")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    if "pytest" in sys.modules:
        object.__setattr__(
            settings,
            "auth_db_path",
            data_dir / f"auth-pytest-{os.getpid()}.sqlite3",
        )
    os.environ.setdefault("HF_HOME", str(settings.hf_home))
    return settings


settings = _load_settings()
