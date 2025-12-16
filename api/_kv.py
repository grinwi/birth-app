import json
import os
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional, Tuple

KV_URL = os.getenv("KV_REST_API_URL", "").rstrip("/")
KV_TOKEN = os.getenv("KV_REST_API_TOKEN", "")
# Development fallback: if KV is not configured, use an in-memory store to avoid hard failures.
USE_DEV_KV = not (KV_URL and KV_TOKEN)
_DEV_STORE: dict[str, str] = {}


class KvError(RuntimeError):
    pass


def _require_kv():
    if USE_DEV_KV:
        # In dev/fallback mode, skip strict requirement
        return
    if not KV_URL or not KV_TOKEN:
        raise KvError("Missing KV_REST_API_URL or KV_REST_API_TOKEN")


def _headers_json():
    return {
        "Authorization": f"Bearer {KV_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "birthdays-app-python",
    }


def _request(method: str, url: str, body: Optional[bytes] = None) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in _headers_json().items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise KvError(f"KV request error: {e}")


def kv_get_raw(key: str) -> Optional[str]:
    """
    GET value as string (or None) from Upstash KV REST.
    GET {KV_URL}/get/{key} -> {"result":"value"} or {"result":null}
    In dev/fallback mode (no KV env), reads from _DEV_STORE.
    """
    if USE_DEV_KV:
        return _DEV_STORE.get(key)
    _require_kv()
    url = f"{KV_URL}/get/{urllib.parse.quote(key, safe='')}"
    status, data = _request("GET", url)
    if status != 200:
        raise KvError(f"KV GET failed: {status} {data.decode('utf-8', 'ignore')}")
    j = json.loads(data.decode("utf-8"))
    return j.get("result")


def kv_set_raw(key: str, value: str, nx: bool = False) -> bool:
    """
    SET raw string value. Returns True if OK.
    POST {KV_URL}/set/{key}/{value}?nx=true|false
    In dev/fallback mode (no KV env), writes to _DEV_STORE.
    """
    if USE_DEV_KV:
        if nx and key in _DEV_STORE:
            return False
        _DEV_STORE[key] = value
        return True
    _require_kv()
    q = "?nx=true" if nx else ""
    url = f"{KV_URL}/set/{urllib.parse.quote(key, safe='')}/{urllib.parse.quote(value, safe='')}{q}"
    status, data = _request("POST", url)
    if status != 200:
        raise KvError(f"KV SET failed: {status} {data.decode('utf-8', 'ignore')}")
    j = json.loads(data.decode("utf-8"))
    # Upstash returns {"result":"OK"} or similar
    return (j.get("result") or "").upper() == "OK"


def kv_del(key: str) -> int:
    """
    DEL key. Returns number of keys removed (0 or 1).
    In dev/fallback mode (no KV env), deletes from _DEV_STORE.
    """
    if USE_DEV_KV:
        if key in _DEV_STORE:
            del _DEV_STORE[key]
            return 1
        return 0
    _require_kv()
    url = f"{KV_URL}/del/{urllib.parse.quote(key, safe='')}"
    status, data = _request("POST", url)
    if status != 200:
        raise KvError(f"KV DEL failed: {status} {data.decode('utf-8', 'ignore')}")
    j = json.loads(data.decode("utf-8"))
    try:
        return int(j.get("result") or 0)
    except Exception:
        return 0


def kv_get_json(key: str, default: Any = None) -> Any:
    raw = kv_get_raw(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def kv_set_json(key: str, value: Any, nx: bool = False) -> bool:
    payload = json.dumps(value, separators=(",", ":"))
    return kv_set_raw(key, payload, nx=nx)


# Domain helpers for this app

BIRTHDAYS_ROWS_KEY = "birthdays_rows"
USERS_KEY = "users"                 # {"username": {"hash": "...", "role": "admin"|"user"}}
INVITE_PREFIX = "invite:"           # invite:<token> -> {"role":"user","created_at":...}


def get_rows() -> list:
    rows = kv_get_json(BIRTHDAYS_ROWS_KEY, default=None)
    return rows if isinstance(rows, list) else []


def set_rows(rows: list) -> None:
    if not isinstance(rows, list):
        raise KvError("rows must be a list")
    kv_set_json(BIRTHDAYS_ROWS_KEY, rows)
