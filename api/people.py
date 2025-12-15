import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from _csv import to_csv, normalize_row, validate_row
from _kv import get_rows as kv_get_rows, set_rows as kv_set_rows
from _github import create_pr_with_csv
from _auth import get_user_from_headers


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
            rows = kv_get_rows()
            _json_response(self, 200, {"data": rows, "count": len(rows)})
        except Exception as e:
            _json_response(self, 500, {"error": f"Failed to read store: {str(e)}"})

    def do_POST(self):
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

            # Load current rows from KV and append
            rows = kv_get_rows()
            rows.append(normalize_row(payload))
            kv_set_rows(rows)

            # Create PR with updated CSV
            new_csv = to_csv(rows) + "\n"
            try:
                pr_number, pr_url = create_pr_with_csv(new_csv, title="Add person via UI")
            except Exception as pe:
                # If PR fails, still return the updated data so UI updates; but indicate failure
                _json_response(self, 201, {"data": rows, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            _json_response(self, 201, {"data": rows, "count": len(rows), "pr_url": pr_url})
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})
