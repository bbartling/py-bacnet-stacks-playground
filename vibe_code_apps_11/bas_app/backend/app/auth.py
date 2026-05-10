"""Demo auth helpers for the BAS backend."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import secrets
from typing import Any


_PBKDF2_ROUNDS = 48_000
_DEMO_SALT = b"bas-demo-auth-v1"


@dataclass(frozen=True, slots=True)
class DemoUser:
    username: str
    full_name: str
    role: str
    password_hash: str


def _hash_password(password: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _DEMO_SALT,
        _PBKDF2_ROUNDS,
    )
    return digest.hex()


def _build_demo_users() -> dict[str, DemoUser]:
    users = (
        DemoUser(
            username="admin",
            full_name="Demo Admin",
            role="Admin",
            password_hash=_hash_password("admin123"),
        ),
        DemoUser(
            username="operator",
            full_name="Demo Operator",
            role="Operator",
            password_hash=_hash_password("operator123"),
        ),
        DemoUser(
            username="readonly",
            full_name="Demo Read Only",
            role="ReadOnly",
            password_hash=_hash_password("readonly123"),
        ),
    )
    return {user.username: user for user in users}


DEMO_USERS = _build_demo_users()
_TOKENS: dict[str, str] = {}


def verify_credentials(username: str, password: str) -> DemoUser | None:
    user = DEMO_USERS.get(username)
    if user is None:
        return None
    candidate_hash = _hash_password(password)
    if not hmac.compare_digest(user.password_hash, candidate_hash):
        return None
    return user


def issue_token(username: str) -> str:
    token = secrets.token_urlsafe(24)
    _TOKENS[token] = username
    return token


def get_user_by_token(token: str) -> DemoUser | None:
    username = _TOKENS.get(token)
    if username is None:
        return None
    return DEMO_USERS.get(username)


def demo_user_payload(user: DemoUser) -> dict[str, Any]:
    return {
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }
