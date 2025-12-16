import base64
import hashlib
import hmac
import json
import os
import time
import secrets
from typing import Dict, Optional, Tuple

from ._kv import kv_get_json, kv_set_json, kv_del, USERS_KEY, INVITE_PREFIX, KvError

AUTH_SECRET = os.getenv("AUTH_SECRET", "")
TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "1209600"))  # 14 days default

class AuthError(RuntimeError):
    pass

def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

def _b64url_decode(s: str) -> bytes:
    pad = 4 - (len(s) % 4)
    if pad and pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))

def _jwt_sign(header: dict, payload: dict, secret: str) -> str:
    if not secret:
        raise AuthError("Missing AUTH_SECRET")
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def _jwt_verify(token: str, secret: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, actual):
            raise AuthError("Invalid token signature")
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if "exp" in payload and int(payload["exp"]) < int(time.time()):
            raise AuthError("Token expired")
        return payload
    except Exception as e:
        raise AuthError("Invalid token") from e

def create_jwt(sub: str, role: str, ttl_sec: int = TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + ttl_sec}
    return _jwt_sign(header, payload, AUTH_SECRET)

def verify_jwt(token: str) -> dict:
    return _jwt_verify(token, AUTH_SECRET)

# Password hashing (PBKDF2-HMAC-SHA256)
def hash_password(password: str, salt: Optional[str] = None, rounds: int = 200_000) -> Tuple[str, str]:
    if salt is None:
        salt = _b64url_encode(secrets.token_bytes(16))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _b64url_decode(salt), rounds)
    return _b64url_encode(dk), salt

def verify_password(password: str, hashed: str, salt: str, rounds: int = 200_000) -> bool:
    dk, _ = hash_password(password, salt=salt, rounds=rounds)
    return hmac.compare_digest(dk, hashed)

# Users storage
def _get_users() -> Dict[str, dict]:
    data = kv_get_json(USERS_KEY, default={})
    return data if isinstance(data, dict) else {}

def _set_users(users: Dict[str, dict]) -> None:
    kv_set_json(USERS_KEY, users)

def user_exists(username: str) -> bool:
    users = _get_users()
    return username in users

def create_user(username: str, password: str, role: str = "user") -> None:
    users = _get_users()
    if username in users:
        raise AuthError("User already exists")
    pwd_hash, salt = hash_password(password)
    users[username] = {"hash": pwd_hash, "salt": salt, "role": role}
    _set_users(users)

def authenticate_user(username: str, password: str) -> Tuple[bool, Optional[str], Optional[str]]:
    users = _get_users()
    u = users.get(username)
    if not u:
        return False, None, None
    ok = verify_password(password, u.get("hash", ""), u.get("salt", ""))
    return ok, username if ok else None, u.get("role") if ok else None

def get_role(username: str) -> Optional[str]:
    users = _get_users()
    u = users.get(username)
    return u.get("role") if u else None

# Invitations
def create_invite(role: str = "user") -> str:
    token = secrets.token_urlsafe(24)
    kv_set_json(f"{INVITE_PREFIX}{token}", {
        "role": role,
        "created_at": int(time.time())
    })
    return token

def consume_invite(token: str) -> Optional[dict]:
    key = f"{INVITE_PREFIX}{token}"
    inv = kv_get_json(key, default=None)
    if inv is None:
        return None
    # One-time consumption
    kv_del(key)
    return inv

# Admin bootstrap on empty user store
def bootstrap_admin_if_empty(username: str, password: str) -> bool:
    """
    If USERS_KEY empty and ADMIN_INITIAL_PASSWORD set,
    allow creating the first admin user by logging in with the configured password.
    """
    users = _get_users()
    if users:
        return False
    initial = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    if not initial:
        return False
    if password != initial or username != "admin":
        return False
    create_user("admin", initial, role="admin")
    return True

# HTTP helpers (cookies)
def parse_cookie(header_val: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not header_val:
        return out
    parts = [p.strip() for p in header_val.split(";")]
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def build_auth_cookie(token: str, secure: bool = True) -> str:
    attrs = [
        f"auth={token}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if secure:
        attrs.append("Secure")
    # 14 days
    attrs.append(f"Max-Age={TOKEN_TTL_SECONDS}")
    return "; ".join(attrs)

def get_user_from_headers(headers) -> Optional[dict]:
    cookie = headers.get("Cookie") or headers.get("cookie")
    m = parse_cookie(cookie)
    tok = m.get("auth")
    if not tok:
        return None
    try:
        payload = verify_jwt(tok)
        return payload
    except Exception:
        return None
