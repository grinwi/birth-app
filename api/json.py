import json
from http.server import BaseHTTPRequestHandler

from ._blob import is_blob_configured, set_json as blob_set_json, get_json as blob_get_json
from ._github import create_pr_with_json
from ._auth import get_user_from_headers


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            rows = blob_get_json(default=[])
            if not isinstance(rows, list):
                rows = []
            _json_response(self, 200, {"data": rows, "count": len(rows)})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_POST(self):
        user = get_user_from_headers(self.headers)
        if not user or user.get("role") != "admin":
            _json_response(self, 403, {"error": "Forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            parsed = json.loads((body or b"{}").decode("utf-8") or "{}")

            if isinstance(parsed, list):
                rows = parsed
            elif isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
                rows = parsed["data"]
            else:
                _json_response(self, 400, {"error": "Unsupported payload format. Provide an array of rows or {\"data\": [...]}."})
                return

            # Persist to Blob (runtime DB) when configured; otherwise skip in dev
            if is_blob_configured():
                blob_set_json(rows)

            # Open PR to update GitHub JSON backup
            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Update birthdays (JSON) via UI")
            except Exception as pe:
                _json_response(self, 200, {"ok": True, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            _json_response(self, 200, {"ok": True, "count": len(rows), "pr_url": pr_url})
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 400, {"error": str(e)})
