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
    Prefer authorized API host to avoid stale public CDN reads.
    """
    if not is_blob_configured():
        return default
    k = key or BLOB_JSON_KEY
    k_path = urllib.parse.quote(k, safe="")

    # Attempt 1: Authorized GET to blob API host
    try:
        status2, data2 = _request("GET", f"https://blob.vercel-storage.com/{k_path}", write=True)
        if status2 == 200:
            try:
                return json.loads(data2.decode("utf-8"))
            except Exception:
                return default
        if status2 == 404:
            return default
    except Exception:
        pass

    # Attempt 2: GET with token query param (no Authorization header) to blob API host
    try:
        if BLOB_READ_WRITE_TOKEN:
            url_q = f"https://blob.vercel-storage.com/{k_path}?token={urllib.parse.quote(BLOB_READ_WRITE_TOKEN, safe='')}"
            status3, data3 = _request("GET", url_q, write=False)
            if status3 == 200:
                try:
                    return json.loads(data3.decode("utf-8"))
                except Exception:
                    return default
            if status3 == 404:
                return default
    except Exception:
        pass

    # Attempt 3: Public bucket GET as last resort
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

    # Give up with explicit error so callers don't treat it as empty (to avoid unintended bootstrap)
    raise BlobError(f"Blob GET failed: {status} {data.decode('utf-8', 'ignore')}")


def set_json(value: Any, key: Optional[str] = None) -> None:
    """
    Write JSON document to Blob.

    Preferred flow (per Vercel Blob REST):
    - POST to https://blob.vercel-storage.com/ with:
        Authorization: Bearer <token>
        Content-Type: application/json
        x-vercel-filename: <key>
        x-vercel-blob-override: true   (allow overwrite/upsert)
      Body: raw file content (the JSON)

    Fallbacks:
    - POST with token query (?token=...) if Authorization header is blocked
    - PUT to https://blob.vercel-storage.com/<key> with Authorization header
    - Legacy attempts to the public bucket URL (may return 405)
    """
    if not is_blob_configured():
        raise BlobError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")

    k = key or BLOB_JSON_KEY
    base = BLOB_BASE_URL.rstrip("/")
    path = urllib.parse.quote(k, safe="")
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")

    attempts = []

    # Attempt 0: PUT to blob.vercel-storage.com/<key> (deterministic key, overwrite in place)
    if BLOB_READ_WRITE_TOKEN:
        url_put = f"https://blob.vercel-storage.com/{path}"
        status_put, data_put = _request("PUT", url_put, body=payload, write=True)  # Authorization + Content-Type
        if status_put in (200, 201):
            return
        attempts.append(f"{status_put} @ {url_put}: {data_put.decode('utf-8','ignore')}")



    # Attempt 3: PUT with Authorization header to the public bucket URL (often 405)
    url1 = f"{base}/{path}"
    status1, data1 = _request("PUT", url1, body=payload, write=True)
    if status1 in (200, 201):
        return
    attempts.append(f"{status1} @ {url1}: {data1.decode('utf-8', 'ignore')}")

    # Attempt 4: PUT with token as query parameter to the public bucket URL
    if BLOB_READ_WRITE_TOKEN:
        url2 = f"{url1}?token={urllib.parse.quote(BLOB_READ_WRITE_TOKEN, safe='')}"
        status2, data2 = _request("PUT", url2, body=payload, write=False)  # no auth header
        if status2 in (200, 201):
            return
        attempts.append(f"{status2} @ {url2}: {data2.decode('utf-8', 'ignore')}")

    raise BlobError("Blob PUT failed; attempts: " + " | ".join(attempts))
