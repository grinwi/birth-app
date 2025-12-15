import json
import os
from http.server import BaseHTTPRequestHandler


def _missing(vars_list):
    return [v for v in vars_list if not (os.getenv(v) or "").strip()]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        blob_vars = ["BLOB_BASE_URL", "BLOB_READ_WRITE_TOKEN", "BLOB_JSON_KEY"]
        github_vars = ["GITHUB_TOKEN", "GITHUB_REPO_OWNER", "GITHUB_REPO", "GITHUB_BRANCH", "GITHUB_JSON_FILE_PATH"]
        auth_vars = ["AUTH_SECRET", "ADMIN_INITIAL_PASSWORD"]
        sync_vars = ["BOOTSTRAP_TOKEN"]

        missing_blob = _missing(blob_vars)
        missing_github = _missing(github_vars)
        missing_auth = _missing(auth_vars)
        missing_sync = _missing(sync_vars)

        blob_configured = len(missing_blob) == 0
        github_configured = len(missing_github) == 0
        auth_configured = len(missing_auth) == 0
        sync_protection_set = len(missing_sync) == 0

        # Build a redacted env preview to help verify values at a glance
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
            "AUTH_SECRET": _redact("AUTH_SECRET", secret=True),
            "ADMIN_INITIAL_PASSWORD": _redact("ADMIN_INITIAL_PASSWORD", secret=True),
            "BOOTSTRAP_TOKEN": _redact("BOOTSTRAP_TOKEN", secret=True),
        }

        status = {
            "ok": blob_configured,
            "blob": {
                "configured": blob_configured,
                "missing": missing_blob,
            },
            "github": {
                "configured": github_configured,
                "missing": missing_github,
            },
            "auth": {
                "configured": auth_configured,
                "missing": missing_auth,
            },
            "sync_protection": {
                "set": sync_protection_set,
                "missing": missing_sync if not sync_protection_set else [],
            },
            "env_preview": env_preview,
            "notes": [
                "Blob must be configured for /api-py/people to succeed: set BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY.",
                "Manual sync (/api-py/sync) is optional. The app will automatically bootstrap Blob from the GitHub JSON snapshot on first read if Blob is empty.",
                "Set GitHub variables and ensure the JSON file exists in the repo (GITHUB_JSON_FILE_PATH)."
            ]
        }

        data = json.dumps(status).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
