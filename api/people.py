import json
import os
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Lazy-import _github only where needed to avoid module import errors at cold start
from ._blob import is_blob_configured, get_json as blob_get_json, set_json as blob_set_json

# In-memory dev storage when Blob is not configured
_DEV_ROWS = None


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
    If Blob is configured but currently empty or invalid, fetch JSON from GitHub
    (using env: GITHUB_REPO_OWNER/REPO/BRANCH/GITHUB_JSON_FILE_PATH) and write it into Blob.
    Returns the rows read (possibly empty).
    """
    owner = (os.getenv("GITHUB_REPO_OWNER") or "").strip()
    repo = (os.getenv("GITHUB_REPO") or "").strip()
    branch = (os.getenv("GITHUB_BRANCH") or "").strip()
    path = (os.getenv("GITHUB_JSON_FILE_PATH") or "").strip()
    if not (owner and repo and branch and path):
        return []
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    try:
        req = urllib.request.Request(raw_url, method="GET", headers={"User-Agent": "birthdays-app-python"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as he:
        if he.code == 404:
            return []
        return []
    except Exception:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            # Persist to Blob and return
            blob_set_json(parsed)
            return parsed
    except Exception:
        return []
    return []


def store_get_rows():
    global _DEV_ROWS
    if not is_blob_configured():
        # Prefer in-memory ephemeral store for dev/unconfigured environments
        if isinstance(_DEV_ROWS, list):
            return _DEV_ROWS
        # Fallback: try reading birthdays.json from repo root or CWD
        candidates = []
        try:
            here = os.path.dirname(__file__)
            candidates.append(os.path.normpath(os.path.join(here, "..", "birthdays.json")))
        except Exception:
            pass
        candidates.append("birthdays.json")
        for p in candidates:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                    if isinstance(parsed, list):
                        _DEV_ROWS = parsed  # cache for subsequent requests
                        return parsed
            except Exception:
                continue
        # No local fallback, return empty list to keep UI functional
        _DEV_ROWS = []
        return _DEV_ROWS
    try:
        data = blob_get_json(default=None)
    except Exception:
        # Fallback when Blob GET errors (e.g., 405/403 or domain/permission issues)
        if isinstance(_DEV_ROWS, list):
            return _DEV_ROWS
        return []
    if isinstance(data, list):
        return data
    # Attempt automatic bootstrap from GitHub JSON if Blob is empty/missing
    rows = _bootstrap_blob_from_github_if_empty()
    return rows


def store_set_rows(rows):
    if not is_blob_configured():
        # Dev/unconfigured: keep rows in-memory to allow UI edits without Blob
        global _DEV_ROWS
        try:
            _DEV_ROWS = list(rows)
        except Exception:
            _DEV_ROWS = rows
        return
    # Blob configured but write may fail (405/403). Fallback to in-memory to avoid breaking the UI.
    try:
        blob_set_json(rows)
    except Exception:
        global _DEV_ROWS
        try:
            _DEV_ROWS = list(rows)
        except Exception:
            _DEV_ROWS = rows
        # swallow write error to keep UX working in dev/misconfigured envs
        return


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _text_response(handler: BaseHTTPRequestHandler, status: int, text: str):
    data = (text or "").encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Reading data does NOT require auth; this allows the UI to bootstrap transparently.
        qs = parse_qs(urlparse(self.path).query or "")
        # On-demand diagnostics (always returns text 200 without attempting store access)
        if "diag" in qs or (qs.get("format") == ["text"]):
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

            # Live probes
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

            lines = [
                "diag: on-demand status",
                f"blob.url: {blob_url}",
                f"blob.status: {blob_get_status}",
                f"github.url: {github_raw_url}",
                f"github.status: {github_get_status}",
                "env_preview:",
                f"  BLOB_BASE_URL: {env_preview['BLOB_BASE_URL']}",
                f"  BLOB_READ_WRITE_TOKEN: {env_preview['BLOB_READ_WRITE_TOKEN']}",
                f"  BLOB_JSON_KEY: {env_preview['BLOB_JSON_KEY']}",
                f"  GITHUB_TOKEN: {env_preview['GITHUB_TOKEN']}",
                f"  GITHUB_REPO_OWNER: {env_preview['GITHUB_REPO_OWNER']}",
                f"  GITHUB_REPO: {env_preview['GITHUB_REPO']}",
                f"  GITHUB_BRANCH: {env_preview['GITHUB_BRANCH']}",
                f"  GITHUB_JSON_FILE_PATH: {env_preview['GITHUB_JSON_FILE_PATH']}",
                "",
                "Hints:",
                "- blob.status 200 => object exists; 404 => empty/missing; other => domain/permission issue.",
                "- github.status 200 => repo JSON reachable; 404 => wrong path/name or missing file.",
                "- If blob is 404 and github is 200, the server should auto-bootstrap on next read."
            ]
            _text_response(self, 200, "\n".join(lines))
            return

        # Force bootstrap from GitHub into Blob (manual trigger for diagnostics)
        if "force_bootstrap" in qs:
            # Build probe URLs
            b_base = (os.getenv("BLOB_BASE_URL") or "").rstrip("/")
            b_key = (os.getenv("BLOB_JSON_KEY") or "").strip()
            owner = (os.getenv("GITHUB_REPO_OWNER") or "").strip()
            repo = (os.getenv("GITHUB_REPO") or "").strip()
            branch = (os.getenv("GITHUB_BRANCH") or "").strip()
            path = (os.getenv("GITHUB_JSON_FILE_PATH") or "").strip()

            blob_url = f"{b_base}/{urllib.parse.quote(b_key, safe='')}" if b_base and b_key else None
            github_raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}" if owner and repo and branch and path else None

            # Try fetching GitHub JSON and writing to Blob
            try:
                raw = None
                gh_status = None
                if github_raw_url:
                    req = urllib.request.Request(github_raw_url, method="GET", headers={"User-Agent": "birthdays-app-python"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        gh_status = resp.getcode()
                        raw = resp.read().decode("utf-8")

                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        try:
                            blob_set_json(parsed)
                            _text_response(self, 200, "\n".join([
                                "force_bootstrap: OK",
                                f"blob.url: {blob_url}",
                                f"github.url: {github_raw_url}",
                                f"rows: {len(parsed)}"
                            ]))
                            return
                        except Exception as be:
                            _text_response(self, 500, "\n".join([
                                "force_bootstrap: failed writing to Blob",
                                f"error: {str(be)}",
                                f"blob.url: {blob_url}",
                                f"github.url: {github_raw_url}"
                            ]))
                            return

                _text_response(self, 500, "\n".join([
                    "force_bootstrap: failed to load GitHub JSON or invalid format",
                    f"blob.url: {blob_url}",
                    f"github.url: {github_raw_url}"
                ]))
                return
            except Exception as e2:
                _text_response(self, 500, "\n".join([
                    "force_bootstrap: unexpected error",
                    f"error: {str(e2)}",
                    f"blob.url: {blob_url}",
                    f"github.url: {github_raw_url}"
                ]))
                return

        try:
            rows = store_get_rows()
            _json_response(self, 200, {"data": rows, "count": len(rows)})
        except Exception as e:
            # Provide detailed diagnostics, including redacted values, plus live probes, to identify misconfiguration
            qs = parse_qs(urlparse(self.path).query or "")
            wants_text = "debug" in qs or (qs.get("format") == ["text"])
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

            payload = {
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
            }
            if wants_text:
                lines = [
                    f"error: {payload['error']}",
                    f"blob.configured: {payload['blob']['configured']}",
                    f"blob.missing: {', '.join(payload['blob']['missing']) or '-'}",
                    f"blob.probe.url: {payload['blob']['probe']['blob_url']}",
                    f"blob.probe.status: {payload['blob']['probe']['blob_get_status']}",
                    f"github.configured: {payload['github']['configured']}",
                    f"github.missing: {', '.join(payload['github']['missing']) or '-'}",
                    f"github.probe.url: {payload['github']['probe']['github_raw_url']}",
                    f"github.probe.status: {payload['github']['probe']['github_get_status']}",
                    "env_preview:",
                    f"  BLOB_BASE_URL: {env_preview['BLOB_BASE_URL']}",
                    f"  BLOB_READ_WRITE_TOKEN: {env_preview['BLOB_READ_WRITE_TOKEN']}",
                    f"  BLOB_JSON_KEY: {env_preview['BLOB_JSON_KEY']}",
                    f"  GITHUB_TOKEN: {env_preview['GITHUB_TOKEN']}",
                    f"  GITHUB_REPO_OWNER: {env_preview['GITHUB_REPO_OWNER']}",
                    f"  GITHUB_REPO: {env_preview['GITHUB_REPO']}",
                    f"  GITHUB_BRANCH: {env_preview['GITHUB_BRANCH']}",
                    f"  GITHUB_JSON_FILE_PATH: {env_preview['GITHUB_JSON_FILE_PATH']}",
                ]
                _text_response(self, 500, "\n".join(lines))
            else:
                _json_response(self, 500, payload)

    def do_POST(self):
        # Mutations still require auth
        try:
            from ._auth import get_user_from_headers as _get_user_from_headers
        except Exception as ie:
            _json_response(self, 500, {"error": f"Auth module import failed: {str(ie)}"})
            return
        user = _get_user_from_headers(self.headers)
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
                from ._github import create_pr_with_json
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
