import json
import os
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from _github import (
    create_pr_with_json,
    fetch_raw_json,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_JSON_FILE_PATH,
)
from _blob import is_blob_configured, get_json as blob_get_json, set_json as blob_set_json
from _auth import get_user_from_headers


def normalize_row(row: dict) -> dict:
    return {
        "first_name": (row.get("first_name") or "").strip(),
        "last_name": (row.get("last_name") or "").strip(),
        "day": (row.get("day") or "").strip(),
        "month": (row.get("month") or "").strip(),
        "year": (row.get("year") or "").strip(),
    }


def validate_row(row: dict) -> None:
    r = normalize_row(row)
    if not r["first_name"]:
        raise ValueError("first_name is required")
    if not r["last_name"]:
        raise ValueError("last_name is required")
    try:
        d = int(r["day"])
        m = int(r["month"])
        y = int(r["year"])
    except Exception:
        raise ValueError("day/month/year must be integers")
    if d < 1 or d > 31:
        raise ValueError("day must be 1-31")
    if m < 1 or m > 12:
        raise ValueError("month must be 1-12")
    if y < 1900 or y > 3000:
        raise ValueError("year must be a realistic year (1900..3000)")
    # Will raise if invalid date
    import datetime
    _ = datetime.date(y, m, d)


def _bootstrap_blob_from_github_if_empty() -> list:
    """
    If Blob is configured but currently empty or invalid, try to read JSON
    from the repository (GITHUB_JSON_FILE_PATH) and write it into Blob.
    Returns the rows read (possibly empty).
    """
    raw = fetch_raw_json(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_JSON_FILE_PATH)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            # Persist to Blob and return
            blob_set_json(parsed)
            return parsed
    except Exception:
        pass
    return []


def store_get_rows():
    if not is_blob_configured():
        # Explicitly signal configuration error
        raise RuntimeError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    data = blob_get_json(default=None)
    if isinstance(data, list):
        return data
    # Attempt automatic bootstrap from GitHub JSON if Blob is empty/missing
    rows = _bootstrap_blob_from_github_if_empty()
    return rows


def store_set_rows(rows):
    if not is_blob_configured():
        raise RuntimeError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    blob_set_json(rows)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Reading data does NOT require auth; this allows the UI to bootstrap transparently.
        try:
            rows = store_get_rows()
            _json_response(self, 200, {"data": rows, "count": len(rows)})
        except Exception as e:
            # Provide detailed diagnostics, including redacted values, plus live probes, to identify misconfiguration
            blob_vars = ["BLOB_BASE_URL", "BLOB_READ_WRITE_TOKEN", "BLOB_JSON_KEY"]
            github_vars = ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO", "GITHUB_BRANCH", "GITHUB_JSON_FILE_PATH"]

            def _redact(name: str, secret: bool = False) -> str:
                v = (os.getenv(name) or "").strip()
                if not v:
                    return ""
                if not secret:
                    return v
                n = len(v)
                if n <= 8:
                    return f"<redacted:{n}>"
                return f"{v[:4]}…{v[-4:]} (len={n})"

            env_preview = {
                "BLOB_BASE_URL": _redact("BLOB_BASE_URL"),
                "BLOB_READ_WRITE_TOKEN": _redact("BLOB_READ_WRITE_TOKEN", secret=True),
                "BLOB_JSON_KEY": _redact("BLOB_JSON_KEY"),
                "GITHUB_TOKEN": _redact("GITHUB_TOKEN", secret=True),
                "GITHUB_REPO_OWNER": _redact("GITHUB_REPO_OWNER"),
                "GITHUB_REPO": _redact("GITHUB_REPO"),
                "GITHUB_BRANCH": _redact("GITHUB_BRANCH"),
                "GITHUB_JSON_FILE_PATH": _redact("GITHUB_JSON_FILE_PATH"),
            }

            missing_blob = [v for v in blob_vars if not (os.getenv(v) or "").strip()]
            missing_github = [v for v in github_vars if not (os.getenv(v) or "").strip()]

            # Live probes (read-only) to help detect common issues
            blob_url = None
            blob_get_status = None
            github_raw_url = None
            github_get_status = None

            try:
                b_base = (os.getenv("BLOB_BASE_URL") or "").rstrip("/")
                b_key = (os.getenv("BLOB_JSON_KEY") or "").strip()
                if b_base and b_key:
                    blob_url = f"{b_base}/{urllib.parse.quote(b_key, safe='')}"
                    req = urllib.request.Request(blob_url, method="GET", headers={"User-Agent": "birthdays-app-python"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        blob_get_status = resp.getcode()
            except urllib.error.HTTPError as he:
                blob_get_status = he.code
            except Exception:
                pass

            try:
                owner = (os.getenv("GITHUB_REPO_OWNER") or "").strip()
                repo = (os.getenv("GITHUB_REPO") or "").strip()
                branch = (os.getenv("GITHUB_BRANCH") or "").strip()
                path = (os.getenv("GITHUB_JSON_FILE_PATH") or "").strip()
                if owner and repo and branch and path:
                    github_raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                    req = urllib.request.Request(github_raw_url, method="GET", headers={"User-Agent": "birthdays-app-python"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        github_get_status = resp.getcode()
            except urllib.error.HTTPError as he:
                github_get_status = he.code
            except Exception:
                pass

            _json_response(self, 500, {
                "ok": False,
                "error": f"Failed to read store: {str(e)}",
                "blob": {
                    "configured": len(missing_blob) == 0,
                    "missing": missing_blob,
                    "probe": {
                        "blob_url": blob_url,
                        "blob_get_status": blob_get_status
                    }
                },
                "github": {
                    "configured": len(missing_github) == 0,
                    "missing": missing_github,
                    "probe": {
                        "github_raw_url": github_raw_url,
                        "github_get_status": github_get_status
                    }
                },
                "env_preview": env_preview,
                "notes": [
                    "If blob_get_status is 404 and github_get_status is 200, bootstrap should succeed on next request.",
                    "If github_get_status is 404, the JSON file path/name is wrong or missing.",
                    "If blob_get_status is not 200/404, verify BLOB_BASE_URL domain and permissions."
                ]
            })

    def do_POST(self):
        # Mutations still require auth
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                _json_response(self, 400, {"error": "Invalid person payload"})
                return

            # Validate row
            try:
                validate_row(payload)
            except Exception as ve:
                _json_response(self, 400, {"error": str(ve)})
                return

            # Load current rows from Blob and append
            rows = store_get_rows()
            rows.append(normalize_row(payload))
            store_set_rows(rows)

            # Create PR with JSON only
            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Add person via UI")
            except Exception as pe:
                # If PR fails, still return the updated data so UI updates; but indicate failure
                _json_response(self, 201, {"data": rows, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            _json_response(self, 201, {"data": rows, "count": len(rows), "pr_url": pr_url})
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})
