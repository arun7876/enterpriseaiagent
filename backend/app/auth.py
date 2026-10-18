import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.config import settings

AUTH_DB_PATH = settings.auth_db_path
JWT_ALGORITHM = "HS256"
JWT_SECRET = settings.jwt_secret
ACCESS_TOKEN_TTL_MINUTES = settings.access_token_ttl_minutes
MAX_LOGIN_ATTEMPTS_PER_MINUTE = 5

RoleName = Literal["admin", "analyst", "viewer"]

_AUTH_ATTEMPTS: dict[str, list[float]] = {}

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthUser(BaseModel):
    id: str
    email: str
    role: RoleName
    created_at: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: RoleName = "analyst"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("role")
    @classmethod
    def public_registration_cannot_create_admin(cls, value: RoleName) -> RoleName:
        if value == "admin":
            raise ValueError("Administrator accounts must be provisioned out of band.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AuthResponse(BaseModel):
    user: AuthUser
    token: str


class LogoutResponse(BaseModel):
    ok: bool = True


class DocumentPermissionRecord(BaseModel):
    document_id: str
    owner_user_id: str
    access_policy: Literal["private", "shared"] = "private"
    shared_with: list[str] = Field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(AUTH_DB_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _initialize_auth_db() -> None:
    AUTH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'analyst', 'viewer')),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS document_permissions (
                document_id TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL,
                access_policy TEXT NOT NULL CHECK(access_policy IN ('private', 'shared')),
                shared_with TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_user_id) REFERENCES users(user_id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS document_shares (
                document_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                PRIMARY KEY(document_id, user_id),
                FOREIGN KEY(document_id) REFERENCES document_permissions(document_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
            """
        )


_initialize_auth_db()


def _rate_limit_key(identifier: str) -> str:
    return identifier.strip().lower()


def _check_rate_limit(identifier: str) -> None:
    key = _rate_limit_key(identifier)
    now = time.time()
    attempts = [timestamp for timestamp in _AUTH_ATTEMPTS.get(key, []) if now - timestamp < 60]
    attempts.append(now)
    _AUTH_ATTEMPTS[key] = attempts
    if len(attempts) > MAX_LOGIN_ATTEMPTS_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again in a minute.",
        )


def _role_is_allowed_for_document(role: RoleName) -> bool:
    return role in {"admin", "analyst", "viewer"}


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _issue_token(user: AuthUser) -> str:
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc


def _user_from_row(row: sqlite3.Row | None) -> AuthUser | None:
    if row is None:
        return None
    return AuthUser(
        id=row["user_id"],
        email=row["email"],
        role=row["role"],
        created_at=row["created_at"],
    )


def ensure_system_user() -> AuthUser:
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id, email, role, created_at FROM users WHERE email = ?",
            ("system@local",),
        ).fetchone()
        if row is not None:
            return _user_from_row(row) or AuthUser(
                id="system",
                email="system@local",
                role="admin",
                created_at=_now_iso(),
            )
        user_id = "system"
        connection.execute(
            "INSERT INTO users(user_id, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, "system@local", _hash_password(uuid.uuid4().hex), "admin", _now_iso()),
        )
        return AuthUser(id=user_id, email="system@local", role="admin", created_at=_now_iso())


def get_user_by_email(email: str) -> AuthUser | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id, email, role, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
        return _user_from_row(row)


def get_user_by_id(user_id: str) -> AuthUser | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id, email, role, created_at FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return _user_from_row(row)


def create_user(email: str, password: str, role: RoleName) -> AuthUser:
    normalized_email = email.strip().lower()
    if get_user_by_email(normalized_email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    user_id = uuid.uuid4().hex
    with _connect() as connection:
        connection.execute(
            "INSERT INTO users(user_id, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, normalized_email, _hash_password(password), role, _now_iso()),
        )
    return AuthUser(id=user_id, email=normalized_email, role=role, created_at=_now_iso())


def authenticate_user(email: str, password: str) -> AuthUser:
    with _connect() as connection:
        row = connection.execute(
            "SELECT user_id, email, password_hash, role, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not _verify_password(password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    return AuthUser(
        id=row["user_id"],
        email=row["email"],
        role=row["role"],
        created_at=row["created_at"],
    )


def _token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()

    cookie_value = request.cookies.get("auth_token")
    if cookie_value:
        return cookie_value
    return None


def get_current_user_optional(request: Request) -> AuthUser | None:
    authorization = request.headers.get("authorization", "")
    uses_bearer_token = authorization.lower().startswith("bearer ")
    cookie_token = request.cookies.get("auth_token")
    if cookie_token and not uses_bearer_token and request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("x-csrf-token")
        if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed.",
            )
    token = _token_from_request(request)
    if not token:
        return None
    try:
        payload = _decode_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        return None
    return get_user_by_id(user_id)


def require_auth(request: Request) -> AuthUser:
    user = get_current_user_optional(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def require_role(role: RoleName, request: Request) -> AuthUser:
    user = require_auth(request)
    if user.role != role and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )
    return user


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.jwt_cookie_secure,
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
    )
    response.set_cookie(
        key="csrf_token",
        value=uuid.uuid4().hex,
        httponly=False,
        samesite="lax",
        secure=settings.jwt_cookie_secure,
        max_age=ACCESS_TOKEN_TTL_MINUTES * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie("auth_token")
    response.delete_cookie("csrf_token")


def ensure_document_permission(document_id: str, owner_user_id: str, access_policy: str = "private") -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO document_permissions(document_id, owner_user_id, access_policy, shared_with, created_at) VALUES (?, ?, ?, '[]', ?) "
            "ON CONFLICT(document_id) DO UPDATE SET owner_user_id = excluded.owner_user_id, access_policy = excluded.access_policy",
            (document_id, owner_user_id, access_policy, _now_iso()),
        )


def update_document_access(document_id: str, owner_user_id: str, access_policy: str = "private") -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO document_permissions(document_id, owner_user_id, access_policy, shared_with, created_at) VALUES (?, ?, ?, '[]', ?) "
            "ON CONFLICT(document_id) DO UPDATE SET access_policy = excluded.access_policy, owner_user_id = excluded.owner_user_id",
            (document_id, owner_user_id, access_policy, _now_iso()),
        )


def add_document_share(document_id: str, user_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO document_shares(document_id, user_id, granted_at) VALUES (?, ?, ?)",
            (document_id, user_id, _now_iso()),
        )
        current = connection.execute(
            "SELECT shared_with FROM document_permissions WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if current is None:
            return
        shared = set()
        if current["shared_with"]:
            shared = set(__import__("json").loads(current["shared_with"]))
        shared.add(user_id)
        connection.execute(
            "UPDATE document_permissions SET shared_with = ?, access_policy = 'shared' WHERE document_id = ?",
            (__import__("json").dumps(sorted(shared)), document_id),
        )


def revoke_document_share(document_id: str, user_id: str) -> None:
    with _connect() as connection:
        connection.execute(
            "DELETE FROM document_shares WHERE document_id = ? AND user_id = ?",
            (document_id, user_id),
        )
        current = connection.execute(
            "SELECT shared_with FROM document_permissions WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if current is not None:
            shared = set(__import__("json").loads(current["shared_with"]))
            shared.discard(user_id)
            connection.execute(
                "UPDATE document_permissions SET shared_with = ?, access_policy = ? WHERE document_id = ?",
                (__import__("json").dumps(sorted(shared)), "private" if not shared else "shared", document_id),
            )


def get_visible_document_ids_for_user(user: AuthUser | None) -> list[str]:
    if user is None:
        return []
    with _connect() as connection:
        if user.role == "admin":
            rows = connection.execute(
                "SELECT document_id FROM document_permissions"
            ).fetchall()
            return [row["document_id"] for row in rows]
        rows = connection.execute(
            "SELECT dp.document_id FROM document_permissions AS dp "
            "LEFT JOIN document_shares AS ds ON ds.document_id = dp.document_id AND ds.user_id = ? "
            "WHERE dp.owner_user_id = ? OR ds.user_id = ?",
            (user.id, user.id, user.id),
        ).fetchall()
        return [row["document_id"] for row in rows]


def user_can_access_document(user: AuthUser | None, document_id: str) -> bool:
    if user is None:
        return False
    if user.role == "admin":
        return True
    with _connect() as connection:
        row = connection.execute(
            "SELECT owner_user_id FROM document_permissions WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        if row is None:
            return False
        if row["owner_user_id"] == user.id:
            return True
        share = connection.execute(
            "SELECT 1 FROM document_shares WHERE document_id = ? AND user_id = ?",
            (document_id, user.id),
        ).fetchone()
        return share is not None


def create_document_permission_record(document_id: str, owner_user_id: str, access_policy: str = "private") -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO document_permissions(document_id, owner_user_id, access_policy, shared_with, created_at) VALUES (?, ?, ?, '[]', ?) "
            "ON CONFLICT(document_id) DO UPDATE SET owner_user_id = excluded.owner_user_id, access_policy = excluded.access_policy",
            (document_id, owner_user_id, access_policy, _now_iso()),
        )


@router.post("/register", response_model=AuthResponse)
def register_user(request: RegisterRequest, response: Response) -> AuthResponse:
    if not settings.allow_self_service_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-service registration is disabled.",
        )
    normalized_email = request.email.strip().lower()
    _check_rate_limit(normalized_email)
    user = create_user(normalized_email, request.password, request.role)
    token = _issue_token(user)
    set_session_cookie(response, token)
    return AuthResponse(user=user, token=token)


@router.post("/login", response_model=AuthResponse)
def login_user(payload: LoginRequest, response: Response) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    _check_rate_limit(normalized_email)
    user = authenticate_user(normalized_email, payload.password)
    token = _issue_token(user)
    set_session_cookie(response, token)
    return AuthResponse(user=user, token=token)


@router.get("/me", response_model=AuthUser)
def me(request: Request) -> AuthUser:
    user = require_auth(request)
    return user


@router.post("/logout", response_model=LogoutResponse)
def logout_user(response: Response, request: Request) -> LogoutResponse:
    clear_session_cookie(response)
    return LogoutResponse(ok=True)


@router.get("/health")
def auth_health() -> dict[str, str]:
    try:
        with _connect() as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return {"status": "unavailable"}
    return {"status": "ok"}
