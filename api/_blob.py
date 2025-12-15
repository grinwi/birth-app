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
    if status == 404:
        return default
    raise BlobError(f"Blob GET failed: {status} {data.decode('utf-8', 'ignore')}")


def set_json(value: Any, key: Optional[str] = None) -> None:
    """
    Write JSON document to Blob.
    """
    if not is_blob_configured():
        raise BlobError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    k = key or BLOB_JSON_KEY
    url = f"{BLOB_BASE_URL}/{urllib.parse.quote(k, safe='')}"
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    # Attempt PUT to the public bucket endpoint with Bearer token.
    # Some configurations may require a different API for write; adjust if needed.
    status, data = _request("PUT", url, body=payload, write=True)
    if status not in (200, 201):
        raise BlobError(f"Blob PUT failed: {status} {data.decode('utf-8', 'ignore')}")
