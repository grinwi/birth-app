import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

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
    import datetime
    _ = datetime.date(y, m, d)


def _bootstrap_blob_from_github_if_empty() -> list:
    """
    If Blob is configured but currently empty or invalid, read JSON
    from the repository (GITHUB_JSON_FILE_PATH) and write it into Blob.
    Returns the rows read (possibly empty).
    """
    raw = fetch_raw_json(GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_JSON_FILE_PATH)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            blob_set_json(parsed)
            return parsed
    except Exception:
        pass
    return []


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
