import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import hashlib
from datetime import datetime, timezone, timedelta

from ._github import (
    create_pr_with_json,
    fetch_raw_json,
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_JSON_FILE_PATH,
)
from ._blob import is_blob_configured, get_json as blob_get_json, set_json as blob_set_json
from ._auth import get_user_from_headers

# In-memory dev storage when Blob is not configured
_DEV_ROWS = None


def normalize_row(row: dict) -> dict:
    return {
        "id": (row.get("id") or "").strip(),
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


def _gen_id_from_dt(dt: datetime) -> str:
    iso = dt.replace(tzinfo=timezone.utc).isoformat()
    return hashlib.sha1(f"birthapp|{iso}".encode("utf-8")).hexdigest()


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
    global _DEV_ROWS
    if not is_blob_configured():
        # Prefer in-memory ephemeral store for dev/unconfigured environments
        if isinstance(_DEV_ROWS, list):
            return _DEV_ROWS
        # Local dev fallback: read from birthdays.json in repo root or CWD
        candidates = []
        try:
            import os
            here = os.path.dirname(__file__)
            candidates.append(os.path.normpath(os.path.join(here, "..", "birthdays.json")))
        except Exception:
            pass
        candidates.append("birthdays.json")
        for p in candidates:
            try:
                with open(p, "r", encoding="utf-8") as f:
                    parsed = json.load(f)
                    if isinstance(parsed, list):
                        return parsed
            except Exception:
                continue
        # No local fallback, return empty list
        return []
    try:
        data = blob_get_json(default=None)
    except Exception:
        # Fallback when Blob GET errors (e.g., 405/403 or domain/permission issues)
        if isinstance(_DEV_ROWS, list):
            return _DEV_ROWS
        return []
    if isinstance(data, list):
        # Backfill missing ids for existing rows and persist once if needed
        needs = False
        for r in data:
            try:
                if not (isinstance(r, dict) and (r.get("id") or "").strip()):
                    needs = True
                    break
            except Exception:
                continue
        if needs:
            base = datetime.now(timezone.utc)
            idx = 0
            for r in data:
                try:
                    if not (isinstance(r, dict) and (r.get("id") or "").strip()):
                        r["id"] = _gen_id_from_dt(base + timedelta(minutes=idx))
                        idx += 1
                except Exception:
                    pass
            try:
                store_set_rows(data)
            except Exception:
                pass
        return data
    # Attempt automatic bootstrap from GitHub JSON if Blob is empty/missing
    rows = _bootstrap_blob_from_github_if_empty()
    return rows


def store_set_rows(rows) -> bool:
    global _DEV_ROWS
    if not is_blob_configured():
        # Dev/unconfigured: keep rows in-memory to allow UI edits without Blob
        try:
            _DEV_ROWS = list(rows)
        except Exception:
            _DEV_ROWS = rows
        return False
    # Blob configured but write may fail (405/403). Fallback to in-memory to avoid breaking the UI.
    try:
        blob_set_json(rows)
        return True
    except Exception:
        try:
            _DEV_ROWS = list(rows)
        except Exception:
            _DEV_ROWS = rows
        # swallow write error to keep UX working in dev/misconfigured envs
        return False


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """
        Method override endpoint for hosts that don't forward PUT/DELETE to Python functions.
        Use header: X-HTTP-Method-Override: PUT|DELETE and ?index=#
        """
        # Auth
        user = get_user_from_headers(self.headers)
        if not user:
            _json_response(self, 401, {"error": "Unauthorized"})
            return

        # Allow override via header or query (?method=PUT|DELETE or ?_method=...)
        qs_for_override = parse_qs(urlparse(self.path).query or "")
        override_q = (qs_for_override.get("method") or qs_for_override.get("_method") or [""])[0]
        override = (self.headers.get("X-HTTP-Method-Override") or override_q or "").strip().upper()
        if override not in ("PUT", "DELETE"):
            # Infer operation when hosts/proxies drop override hints:
            # if body present => treat as PUT, otherwise DELETE.
            try:
                content_len = int(self.headers.get("Content-Length", "0"))
            except Exception:
                content_len = 0
            override = "PUT" if content_len > 0 else "DELETE"

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

            rows = store_get_rows()

            if override == "PUT":
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

                if idx >= len(rows):
                    _json_response(self, 400, {"error": "Index out of range"})
                    return

                updated = normalize_row(payload)
                try:
                    existing_id = rows[idx].get("id")
                except Exception:
                    existing_id = None
                if not (updated.get("id") or "") and existing_id:
                    updated["id"] = existing_id
                # Transactional flow: write Blob -> PR -> else revert Blob and error
                if not is_blob_configured():
                    _json_response(self, 503, {"ok": False, "error": "Blob not configured"})
                    return

                rows_old = json.loads(json.dumps(rows))
                rows[idx] = updated
                try:
                    blob_set_json(rows)
                except Exception as be:
                    _json_response(self, 500, {"ok": False, "error": f"Blob write failed: {str(be)}"})
                    return

                try:
                    pr_number, pr_url = create_pr_with_json(rows, title="Update person via UI")
                except Exception as pe:
                    reverted = True
                    try:
                        blob_set_json(rows_old)
                    except Exception:
                        reverted = False
                    _json_response(self, 500, {"ok": False, "error": f"PR creation failed: {str(pe)}", "reverted": reverted})
                    return

                _json_response(self, 200, {"ok": True, "data": rows, "count": len(rows), "pr_url": pr_url})
                return

            if override == "DELETE":
                if idx >= len(rows):
                    _json_response(self, 400, {"error": "Index out of range"})
                    return
                # Transactional flow: write Blob -> PR -> else revert Blob and error
                if not is_blob_configured():
                    _json_response(self, 503, {"ok": False, "error": "Blob not configured"})
                    return

                rows_old = json.loads(json.dumps(rows))
                rows.pop(idx)
                try:
                    blob_set_json(rows)
                except Exception as be:
                    _json_response(self, 500, {"ok": False, "error": f"Blob write failed: {str(be)}"})
                    return

                try:
                    pr_number, pr_url = create_pr_with_json(rows, title="Delete person via UI")
                except Exception as pe:
                    reverted = True
                    try:
                        blob_set_json(rows_old)
                    except Exception:
                        reverted = False
                    _json_response(self, 500, {"ok": False, "error": f"PR creation failed: {str(pe)}", "reverted": reverted})
                    return

                _json_response(self, 200, {"ok": True, "data": rows, "count": len(rows), "pr_url": pr_url})
                return

            _json_response(self, 405, {"error": "Method Not Allowed"})
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "Invalid JSON"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

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
            updated = normalize_row(payload)
            try:
                existing_id = rows[idx].get("id")
            except Exception:
                existing_id = None
            if not (updated.get("id") or "") and existing_id:
                updated["id"] = existing_id
            # Transactional flow: write Blob -> PR -> else revert Blob and error
            if not is_blob_configured():
                _json_response(self, 503, {"ok": False, "error": "Blob not configured"})
                return

            rows_old = json.loads(json.dumps(rows))
            rows[idx] = updated
            try:
                blob_set_json(rows)
            except Exception as be:
                _json_response(self, 500, {"ok": False, "error": f"Blob write failed: {str(be)}"})
                return

            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Update person via UI")
            except Exception as pe:
                reverted = True
                try:
                    blob_set_json(rows_old)
                except Exception:
                    reverted = False
                _json_response(self, 500, {"ok": False, "error": f"PR creation failed: {str(pe)}", "reverted": reverted})
                return

            _json_response(self, 200, {"ok": True, "data": rows, "count": len(rows), "pr_url": pr_url})
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
            # Transactional flow: write Blob -> PR -> else revert Blob and error
            if not is_blob_configured():
                _json_response(self, 503, {"ok": False, "error": "Blob not configured"})
                return

            rows_old = json.loads(json.dumps(rows))
            rows.pop(idx)
            try:
                blob_set_json(rows)
            except Exception as be:
                _json_response(self, 500, {"ok": False, "error": f"Blob write failed: {str(be)}"})
                return

            try:
                pr_number, pr_url = create_pr_with_json(rows, title="Delete person via UI")
            except Exception as pe:
                reverted = True
                try:
                    blob_set_json(rows_old)
                except Exception:
                    reverted = False
                _json_response(self, 500, {"ok": False, "error": f"PR creation failed: {str(pe)}", "reverted": reverted})
                return

            _json_response(self, 200, {"ok": True, "data": rows, "count": len(rows), "pr_url": pr_url})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})
