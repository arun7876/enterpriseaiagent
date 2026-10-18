import uuid

import pytest

from backend.app.auth import AuthUser, _issue_token, create_user


@pytest.fixture
def auth_user() -> AuthUser:
    return create_user(
        f"test-{uuid.uuid4().hex}@example.com",
        "StrongPass123",
        "analyst",
    )


@pytest.fixture
def auth_headers(auth_user: AuthUser) -> dict[str, str]:
    user = auth_user
    return {"Authorization": f"Bearer {_issue_token(user)}"}
