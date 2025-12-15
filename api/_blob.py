import json
import os
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional, Tuple

# Configuration for Vercel Blob (simple REST usage)
# Provide the public/read URL base for your blob store and a read/write token.
# Examples:
#   BLOB_BASE_URL = "https://your-bucket-id.public.blob.vercel-storage.com"
#   BLOB_READ_WRITE_TOKEN = "<vercel-blob-read-write-token>"
#   BLOB_JSON_KEY = "birthdays.json"
BLOB_BASE_URL = (os.getenv("BLOB_BASE_URL") or "").rstrip("/")
BLOB_READ_WRITE_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN") or ""
BLOB_JSON_KEY = os.getenv("BLOB_JSON_KEY") or "birthdays.json"



class BlobError(RuntimeError):
    pass


def is_blob_configured() -> bool:
    return bool(BLOB_BASE_URL and BLOB_READ_WRITE_TOKEN and BLOB_JSON_KEY)


def _headers_json(write: bool = False) -> dict:
    headers = {
        "Accept": "application/json",
        "User-Agent": "birthdays-app-python",
    }
    if write:
        headers["Authorization"] = f"Bearer {BLOB_READ_WRITE_TOKEN}"
        headers["Content-Type"] = "application/json"
    return headers


def _request(method: str, url: str, body: Optional[bytes] = None, write: bool = False) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in _headers_json(write=write).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise BlobError(f"Blob request error: {e}")


def get_json(key: Optional[str] = None, default: Any = None) -> Any:
    """
    Read JSON document from Blob. Returns `default` if missing (404).
    """
    if not is_blob_configured():
        return default
    k = key or BLOB_JSON_KEY
    url = f"{BLOB_BASE_URL}/{urllib.parse.quote(k, safe='')}"
    status, data = _request("GET", url)
    if status == 200:
        try:
            text = data.decode("utf-8")
            return json.loads(text)
        except Exception:
            return default
    if status in (404, 403):
        # Treat 403 similar to missing for public buckets to allow bootstrap
        return default
    raise BlobError(f"Blob GET failed: {status} {data.decode('utf-8', 'ignore')}")


def set_json(value: Any, key: Optional[str] = None) -> None:
    """
    Write JSON document to Blob.
    Tries multiple strategies for compatibility with different Blob configurations.
    """
    if not is_blob_configured():
        raise BlobError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    k = key or BLOB_JSON_KEY
    base = BLOB_BASE_URL.rstrip("/")
    path = urllib.parse.quote(k, safe="")
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")

    attempts = []

    # Attempt 1: PUT with Authorization header to the public bucket URL
    url1 = f"{base}/{path}"
    status1, data1 = _request("PUT", url1, body=payload, write=True)
    if status1 in (200, 201):
        return
    attempts.append(f"{status1} @ {url1}: {data1.decode('utf-8', 'ignore')}")

    # Attempt 2: PUT with token as query parameter (some setups accept ?token=)
    if BLOB_READ_WRITE_TOKEN:
        url2 = f"{url1}?token={urllib.parse.quote(BLOB_READ_WRITE_TOKEN, safe='')}"
        status2, data2 = _request("PUT", url2, body=payload, write=False)  # no auth header
        if status2 in (200, 201):
            return
        attempts.append(f"{status2} @ {url2}: {data2.decode('utf-8', 'ignore')}")

    # Attempt 3: PUT to generic upload host (compat fallback)
    try:
        if BLOB_READ_WRITE_TOKEN:
            url3 = f"https://blob.vercel-storage.com/{path}?token={urllib.parse.quote(BLOB_READ_WRITE_TOKEN, safe='')}"
            status3, data3 = _request("PUT", url3, body=payload, write=False)
            if status3 in (200, 201):
                return
            attempts.append(f"{status3} @ https://blob.vercel-storage.com/{path}: {data3.decode('utf-8', 'ignore')}")
    except Exception as e:
        attempts.append(f"fallback error: {e}")

    raise BlobError("Blob PUT failed; attempts: " + " | ".join(attempts))
