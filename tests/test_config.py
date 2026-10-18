from dataclasses import replace

import pytest

from backend.app.config import settings


def test_production_requires_generated_secret_secure_cookies_and_https_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://research.example.com")
    production = replace(
        settings,
        app_env="production",
        jwt_secret="A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
        jwt_cookie_secure=True,
        allow_self_service_registration=False,
        cors_allowed_origins=("https://research.example.com",),
    )

    production.validate()

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        replace(production, jwt_secret="replace-with-a-random-secret-of-at-least-32-characters").validate()
    with pytest.raises(RuntimeError, match="JWT_COOKIE_SECURE"):
        replace(production, jwt_cookie_secure=False).validate()
    with pytest.raises(RuntimeError, match="ALLOW_SELF_SERVICE_REGISTRATION"):
        replace(production, allow_self_service_registration=True).validate()


def test_settings_reject_invalid_upload_and_logging_values() -> None:
    with pytest.raises(RuntimeError, match="MAX_UPLOAD_SIZE_BYTES"):
        replace(settings, max_upload_size_bytes=0).validate()
    with pytest.raises(RuntimeError, match="LOG_LEVEL"):
        replace(settings, log_level="NOT_A_LEVEL").validate()
    with pytest.raises(RuntimeError, match="ACCESS_TOKEN_TTL_MINUTES"):
        replace(settings, access_token_ttl_minutes=0).validate()
    with pytest.raises(RuntimeError, match="APP_ENV"):
        replace(settings, app_env="invalid_environment").validate()
    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        replace(settings, cors_allowed_origins=()).validate()
    with pytest.raises(RuntimeError, match="OLLAMA_TIMEOUT_SECONDS"):
        replace(settings, ollama_timeout_seconds=0).validate()
    with pytest.raises(RuntimeError, match="RAG_MIN_RELEVANCE_SCORE"):
        replace(settings, rag_min_relevance_score=-0.1).validate()
    with pytest.raises(RuntimeError, match="RAG_MIN_RELEVANCE_SCORE"):
        replace(settings, rag_min_relevance_score=1.5).validate()
