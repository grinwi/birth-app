import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from ._blob import is_blob_configured, set_json as blob_set_json, get_json as blob_get_json
from ._github import create_pr_with_json
from ._auth import get_user_from_headers

def _normalize_row(row: dict) -> dict:
    return {
        "first_name": (row.get("first_name") or "").strip(),
        "last_name": (row.get("last_name") or "").strip(),
        "day": (row.get("day") or "").strip(),
        "month": (row.get("month") or "").strip(),
        "year": (row.get("year") or "").strip(),
    }

def _validate_row(row: dict) -> None:
    r = _normalize_row(row)
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

            # Strict validation toggle via ?strict=false (default is strict validation)
            qs = parse_qs(urlparse(self.path).query or "")
            strict = (qs.get("strict", ["true"])[0].lower() != "false")

            # Validate all rows with clear indexing; in non-strict mode collect warnings instead of failing
            warnings = []
            for i, r in enumerate(rows):
                try:
                    _validate_row(r if isinstance(r, dict) else {})
                except Exception as ve:
                    if strict:
                        _json_response(self, 400, {"error": f"Row {i}: {str(ve)}"})
                        return
                    warnings.append(f"Row {i}: {str(ve)}")

            # Persist to Blob (runtime DB) when configured; otherwise skip in dev
            if is_blob_configured():
                blob_set_json(rows)

            # Open PR to update GitHub JSON backup
            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Update birthdays (JSON) via UI")
            except Exception as pe:
                _json_response(self, 200, {"ok": True, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
                return

            resp = {"ok": True, "count": len(rows), "pr_url": pr_url}
            if warnings:
                resp["warning"] = "; ".join(warnings)
            _json_response(self, 200, resp)
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 400, {"error": str(e)})
