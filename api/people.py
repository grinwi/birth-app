import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from _csv import normalize_row, validate_row
from _github import create_pr_with_json
from _blob import is_blob_configured, get_json as blob_get_json, set_json as blob_set_json
from _auth import get_user_from_headers


def store_get_rows():
    if not is_blob_configured():
        raise RuntimeError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    data = blob_get_json(default=[])
    return data if isinstance(data, list) else []

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
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            rows = store_get_rows()
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
