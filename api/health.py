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
            "notes": [
                "Blob must be configured and initialized for /api-py/people to succeed.",
                "Use POST /api-py/sync with BOOTSTRAP_TOKEN to populate Blob from the GitHub JSON snapshot after deployment."
            ]
        }

        data = json.dumps(status).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
