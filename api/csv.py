import json
from http.server import BaseHTTPRequestHandler

from _csv import parse_csv, to_csv
from _kv import get_rows as kv_get_rows, set_rows as kv_set_rows
from _github import (
  create_pr_with_csv,
)
from _auth import get_user_from_headers


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
  data = json.dumps(payload).encode("utf-8")
  handler.send_response(status)
  handler.send_header("Content-Type", "application/json; charset=utf-8")
  handler.send_header("Content-Length", str(len(data)))
  handler.end_headers()
  handler.wfile.write(data)


def _text_response(handler: BaseHTTPRequestHandler, status: int, text: str, content_type: str = "text/plain; charset=utf-8"):
  data = (text or "").encode("utf-8")
  handler.send_response(status)
  handler.send_header("Content-Type", content_type)
  handler.send_header("Content-Length", str(len(data)))
  handler.end_headers()
  handler.wfile.write(data)


class handler(BaseHTTPRequestHandler):
  # GET -> return current birthdays.csv (from GitHub main)
  def do_GET(self):
    user = get_user_from_headers(self.headers)
    if not user:
      _text_response(self, 401, "Unauthorized", "text/plain; charset=utf-8")
      return
    try:
      rows = kv_get_rows()
      csv_text = to_csv(rows) + "\n"
      _text_response(self, 200, csv_text, "text/csv; charset=utf-8")
    except Exception as e:
      _text_response(self, 404, "CSV not found", "text/plain; charset=utf-8")

  # POST -> accept CSV or JSON rows and open a PR with the updated file
  def do_POST(self):
    user = get_user_from_headers(self.headers)
    if not user or user.get("role") != "admin":
      _text_response(self, 403, "Forbidden", "application/json; charset=utf-8")
      return
    try:
      ct = (self.headers.get("Content-Type") or "").lower()
      length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(length) if length > 0 else b""

      rows = []
      if "text/csv" in ct:
        csv_text = (body or b"").decode("utf-8")
        if not csv_text or len(csv_text.strip()) < 10:
          _text_response(self, 400, "Invalid or empty CSV")
          return
        rows = parse_csv(csv_text)
      elif "application/json" in ct:
        try:
          parsed = json.loads((body or b"{}").decode("utf-8") or "{}")
        except json.JSONDecodeError:
          _text_response(self, 400, "Invalid JSON")
          return
        if isinstance(parsed, list):
          rows = parsed
        elif isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
          rows = parsed["data"]
        else:
          _text_response(self, 400, "Unsupported payload format")
          return
      else:
        # Best-effort: treat as CSV text
        csv_text = (body or b"").decode("utf-8")
        if not csv_text or len(csv_text.strip()) < 10:
          _text_response(self, 400, "Unsupported payload format")
          return
        rows = parse_csv(csv_text)

      kv_set_rows(rows)
      new_csv = to_csv(rows) + "\n"
      try:
        pr_number, pr_url = create_pr_with_csv(new_csv, title="Update birthdays.csv via UI")
      except Exception as pe:
        _json_response(self, 200, {"ok": True, "count": len(rows), "pr_url": None, "warning": f"PR creation failed: {str(pe)}"})
        return

      _json_response(self, 200, {"ok": True, "count": len(rows), "pr_url": pr_url})
    except Exception as e:
      _text_response(self, 400, str(e))
