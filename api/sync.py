import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from ._blob import is_blob_configured, set_json as blob_set_json
from ._github import (
    fetch_raw_json,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_JSON_FILE_PATH,
)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _authorized(handler: BaseHTTPRequestHandler) -> bool:
    """
    Simple bearer-token gate for bootstrap/sync.
    Accepts either:
      - Authorization: Bearer <BOOTSTRAP_TOKEN>
      - X-Bootstrap-Token: <BOOTSTRAP_TOKEN>
      - ?token=<BOOTSTRAP_TOKEN> (query param)
    """
    expected = os.getenv("BOOTSTRAP_TOKEN", "")
    if not expected:
        return False

    # Header Authorization: Bearer ...
    auth = handler.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        if auth.split(" ", 1)[1].strip() == expected:
            return True

    # Header X-Bootstrap-Token
    xbt = handler.headers.get("X-Bootstrap-Token") or ""
    if xbt.strip() == expected:
        return True

    # Query param ?token=
    qs = parse_qs(urlparse(handler.path).query or "")
    token_vals = qs.get("token", [])
    if token_vals and token_vals[0].strip() == expected:
        return True

    return False


def _load_rows_from_github() -> list:
    raw = fetch_raw_json(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_JSON_FILE_PATH)
    if not raw:
        # empty/missing treated as empty dataset
        return []
    try:
        parsed = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Invalid JSON in GitHub file {GITHUB_JSON_FILE_PATH}: {e}")
    if not isinstance(parsed, list):
        raise RuntimeError(f"GitHub JSON {GITHUB_JSON_FILE_PATH} must be a JSON array of rows")
    return parsed


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """
        Dry-run/status: fetch JSON from GitHub and report counts (no writes).
        Auth required (same as POST).
        """
        if not _authorized(self):
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            rows = _load_rows_from_github()
            _json_response(self, 200, {
                "ok": True,
                "github_owner": GITHUB_OWNER,
                "github_repo": GITHUB_REPO,
                "github_branch": GITHUB_BRANCH,
                "github_json_path": GITHUB_JSON_FILE_PATH,
                "count": len(rows)
            })
        except Exception as e:
            _json_response(self, 400, {"error": str(e)})

    def do_POST(self):
        """
        Perform sync: load JSON from GitHub, write to Blob (runtime source of truth).
        Auth required via BOOTSTRAP_TOKEN.
        """
        if not _authorized(self):
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            if not is_blob_configured():
                _json_response(self, 500, {"error": "Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)"})
                return

            rows = _load_rows_from_github()
            blob_set_json(rows)
            _json_response(self, 200, {
                "ok": True,
                "written": len(rows),
                "github_owner": GITHUB_OWNER,
                "github_repo": GITHUB_REPO,
                "github_branch": GITHUB_BRANCH,
                "github_json_path": GITHUB_JSON_FILE_PATH
            })
        except Exception as e:
            _json_response(self, 400, {"error": str(e)})
