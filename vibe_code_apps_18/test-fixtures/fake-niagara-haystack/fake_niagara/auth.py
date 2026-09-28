"""Project Haystack SCRAM-SHA-256 HTTP authentication primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
import uuid
from dataclasses import dataclass


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def ub64(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"), validate=True)


def _hmac(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def _scram_user(username: str) -> str:
    return username.replace("=", "=3D").replace(",", "=2C")


def derive_credentials(password: str, salt: bytes, iterations: int = 4096) -> tuple[bytes, bytes]:
    """Return SCRAM StoredKey and ServerKey for a password."""
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = _hmac(salted, b"Client Key")
    return hashlib.sha256(client_key).digest(), _hmac(salted, b"Server Key")


@dataclass
class User:
    username: str
    salt: bytes
    iterations: int
    stored_key: bytes
    server_key: bytes

    @classmethod
    def from_password(cls, username: str, password: str, *, salt: bytes | None = None, iterations: int = 4096) -> "User":
        salt = salt or secrets.token_bytes(16)
        stored, server = derive_credentials(password, salt, iterations)
        return cls(username, salt, iterations, stored, server)


@dataclass
class Handshake:
    username: str
    known_user: bool
    outer_urlsafe: bool
    created: float
    stage: str = "hello"
    client_nonce: str = ""
    server_nonce: str = ""
    server_first: str = ""
    auth_message: str = ""
    server_signature: bytes = b""
    stored_key: bytes = b""


class AuthManager:
    def __init__(self, users: dict[str, str], token_ttl: int = 86400, handshake_ttl: int = 120, max_handshakes: int = 256, max_tokens: int = 2048) -> None:
        self.users = {name: User.from_password(name, password) for name, password in users.items()}
        self.token_ttl = token_ttl
        self.handshake_ttl = handshake_ttl
        self.max_handshakes = max_handshakes
        self.max_tokens = max_tokens
        self._handshakes: dict[str, Handshake] = {}
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _params(header: str) -> tuple[str, dict[str, str]]:
        bits = header.strip().split(None, 1)
        scheme = bits[0].upper() if bits else ""
        params: dict[str, str] = {}
        if len(bits) == 2:
            for part in bits[1].split(","):
                if "=" in part:
                    key, val = part.strip().split("=", 1)
                    params[key] = val.strip()
        return scheme, params

    def hello(self, username_b64: str, client_first_b64: str | None) -> tuple[int, dict[str, str]]:
        try:
            outer_urlsafe = "-" in username_b64 or "_" in username_b64 or "=" not in username_b64
            username = _decode_outer(username_b64).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            username = ""
        user = self.users.get(username)
        # Use deterministic-looking fake credentials for unknown users to avoid
        # leaking account existence, but never issue a token for them.
        if user is None:
            user = User.from_password(username or "unknown", "invalid", salt=b"fake-haystack-salt")
        handshake_token = secrets.token_urlsafe(18)
        hs = Handshake(username, username in self.users, outer_urlsafe, time.time())
        with self._lock:
            self._purge_locked()
            if len(self._handshakes) >= self.max_handshakes:
                self._handshakes.pop(next(iter(self._handshakes)))
            self._handshakes[handshake_token] = hs
        if not client_first_b64:
            return 401, {"WWW-Authenticate": f"SCRAM hash=SHA-256, handshakeToken={handshake_token}"}
        # rusty-haystack currently sends the SCRAM client-first payload on the
        # HELLO request. Keep accepting it while the standards path below uses
        # HELLO(no data) -> SCRAM(client-first) -> SCRAM(client-final).
        status, headers = self._start_scram(handshake_token, client_first_b64)
        return status, headers

    def _start_scram(self, handshake_token: str, client_first_b64: str) -> tuple[int, dict[str, str]]:
        with self._lock:
            hs = self._handshakes.get(handshake_token)
        if hs is None or time.time() - hs.created > self.handshake_ttl:
            return 403, {}
        user = self.users.get(hs.username)
        if user is None:
            user = User.from_password(hs.username or "unknown", "invalid", salt=b"fake-haystack-salt")
        username = hs.username
        try:
            first = _decode_outer(client_first_b64).decode("utf-8")
            if not first.startswith("n,,"):
                raise ValueError("missing GS2 header")
            parts = first[3:].split(",")
            nonce = next(x[2:] for x in parts if x.startswith("r="))
        except (ValueError, StopIteration, UnicodeDecodeError):
            return 403, {}
        server_nonce = b64(secrets.token_bytes(18))
        combined = nonce + server_nonce
        server_first = f"r={combined},s={b64(user.salt)},i={user.iterations}"
        client_bare = f"n={_scram_user(username)},r={nonce}"
        client_final_no_proof = f"c=biws,r={combined}"
        auth_message = f"{client_bare},{server_first},{client_final_no_proof}"
        hs.client_nonce = nonce
        hs.server_nonce = server_nonce
        hs.server_first = server_first
        hs.auth_message = auth_message
        hs.server_signature = _hmac(user.server_key, auth_message.encode())
        hs.stored_key = user.stored_key
        hs.stage = "final"
        with self._lock:
            self._handshakes[handshake_token] = hs
        challenge_data = _encode_outer(server_first.encode(), hs.outer_urlsafe)
        return 401, {"WWW-Authenticate": f"SCRAM handshakeToken={handshake_token}, hash=SHA-256, data={challenge_data}"}

    def scram(self, handshake_token: str, client_final_b64: str) -> tuple[int, dict[str, str]]:
        with self._lock:
            hs = self._handshakes.get(handshake_token)
        if hs is None or time.time() - hs.created > self.handshake_ttl:
            return 403, {}
        if hs.stage == "hello":
            return self._start_scram(handshake_token, client_final_b64)
        with self._lock:
            # A client-final is single-use even when verification fails.
            self._handshakes.pop(handshake_token, None)
        if not hs.known_user:
            return 403, {}
        try:
            final = _decode_outer(client_final_b64).decode("utf-8")
            parts = final.split(",")
            values = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in parts if "=" in part}
            if values.get("c") != "biws" or values.get("r") != hs.client_nonce + hs.server_nonce:
                return 403, {}
            proof = ub64(values["p"])
            signature = _hmac(hs.stored_key, hs.auth_message.encode())
            recovered = bytes(a ^ b for a, b in zip(proof, signature))
            if not hmac.compare_digest(hashlib.sha256(recovered).digest(), hs.stored_key):
                return 403, {}
        except (ValueError, KeyError, UnicodeDecodeError):
            return 403, {}
        token = uuid.uuid4().hex
        with self._lock:
            self._purge_locked()
            if len(self._tokens) >= self.max_tokens:
                self._tokens.pop(next(iter(self._tokens)))
            self._tokens[token] = (hs.username, time.time() + self.token_ttl)
        server_final = _encode_outer(f"v={b64(hs.server_signature)}".encode(), hs.outer_urlsafe)
        return 200, {"Authentication-Info": f"authToken={token}, hash=SHA-256, data={server_final}"}

    def authenticate_header(self, header: str | None) -> str | None:
        if not header:
            return None
        scheme, params = self._params(header)
        if scheme != "BEARER" or not params.get("authToken"):
            return None
        token = params["authToken"]
        with self._lock:
            self._purge_locked()
            item = self._tokens.get(token)
            if item and item[1] > time.time():
                return item[0]
            self._tokens.pop(token, None)
        return None

    def close(self, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            return self._tokens.pop(token, None) is not None

    def _purge_locked(self) -> None:
        now = time.time()
        self._handshakes = {key: value for key, value in self._handshakes.items() if now - value.created <= self.handshake_ttl}
        self._tokens = {key: value for key, value in self._tokens.items() if value[1] > now}


def _decode_outer(value: str) -> bytes:
    # Haystack outer auth values are base64url without padding. rusty-haystack
    # currently uses padded standard base64; accepting both keeps the simulator
    # useful for both clients.
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.b64decode(padded.encode("ascii"), validate=True)
    except (ValueError, base64.binascii.Error):
        return base64.urlsafe_b64decode(padded.encode("ascii"))


def _encode_outer(data: bytes, urlsafe: bool) -> str:
    if urlsafe:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
    return b64(data)
