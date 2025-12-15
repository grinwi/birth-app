import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from _csv import normalize_row, validate_row
from _github import create_pr_with_json
from _blob import is_blob_configured, get_json as blob_get_json, set_json as blob_set_json
from _auth import get_user_from_headers


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def store_get_rows():
    if not is_blob_configured():
        raise RuntimeError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    data = blob_get_json(default=[])
    return data if isinstance(data, list) else []


def store_set_rows(rows):
    if not is_blob_configured():
        raise RuntimeError("Blob is not configured (BLOB_BASE_URL, BLOB_READ_WRITE_TOKEN, BLOB_JSON_KEY)")
    blob_set_json(rows)


class handler(BaseHTTPRequestHandler):
    def do_PUT(self):
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            # Parse index from query ?index=#
            qs = parse_qs(urlparse(self.path).query or "")
            index_vals = qs.get("index", [])
            if not index_vals:
                _json_response(self, 400, {"error": "Missing index"})
                return
            try:
                idx = int(index_vals[0])
                if idx < 0:
                    raise ValueError()
            except Exception:
                _json_response(self, 400, {"error": "Invalid index"})
                return

            # Read JSON body for updated person
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                _json_response(self, 400, {"error": "Invalid person payload"})
                return

            # Validate
            try:
                validate_row(payload)
            except Exception as ve:
                _json_response(self, 400, {"error": str(ve)})
                return

            # Load current rows from KV, update at index
            rows = store_get_rows()
            if idx >= len(rows):
                _json_response(self, 400, {"error": "Index out of range"})
                return
            rows[idx] = normalize_row(payload)
            store_set_rows(rows)

            # Create PR with JSON only
            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Update person via UI")
            except Exception as pe:
                _json_response(self, 200, {"data": rows, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            _json_response(self, 200, {"data": rows, "count": len(rows), "pr_url": pr_url})
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_DELETE(self):
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        try:
            # Parse index from query ?index=#
            qs = parse_qs(urlparse(self.path).query or "")
            index_vals = qs.get("index", [])
            if not index_vals:
                _json_response(self, 400, {"error": "Missing index"})
                return
            try:
                idx = int(index_vals[0])
                if idx < 0:
                    raise ValueError()
            except Exception:
                _json_response(self, 400, {"error": "Invalid index"})
                return

            # Load current rows from KV and delete at index
            rows = store_get_rows()
            if idx >= len(rows):
                _json_response(self, 400, {"error": "Index out of range"})
                return
            rows.pop(idx)
            store_set_rows(rows)

            # Create PR with JSON only
            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Delete person via UI")
            except Exception as pe:
                _json_response(self, 200, {"data": rows, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            _json_response(self, 200, {"data": rows, "count": len(rows), "pr_url": pr_url})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})
