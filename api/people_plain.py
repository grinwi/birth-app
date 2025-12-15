import json
import os
from http.server import BaseHTTPRequestHandler


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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
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
        payload = {
            "ok": True,
            "message": "people_plain diagnostic endpoint alive",
            "env_preview": env_preview,
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
