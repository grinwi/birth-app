import json
from http.server import BaseHTTPRequestHandler

from .._auth import create_invite, get_user_from_headers

def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict):
  data = json.dumps(payload).encode("utf-8")
  handler.send_response(status)
  handler.send_header("Content-Type", "application/json; charset=utf-8")
  handler.send_header("Content-Length", str(len(data)))
  handler.end_headers()
  handler.wfile.write(data)

class handler(BaseHTTPRequestHandler):
  # POST {"role": "user"|"admin"}  (admin only)
  def do_POST(self):
    user = get_user_from_headers(self.headers)
    if not user or (user.get("role") != "admin"):
      _json(self, 403, {"error": "Forbidden"})
      return

    try:
      length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(length) if length > 0 else b"{}"
      payload = json.loads(body.decode("utf-8") or "{}")
      role = (payload.get("role") or "user").strip().lower()
      if role not in ("user", "admin"):
        role = "user"

      token = create_invite(role=role)

      # Return token; frontend can compose a registration URL like /register?invite=TOKEN
      _json(self, 200, {"ok": True, "token": token})
    except json.JSONDecodeError:
      _json(self, 400, {"error": "Invalid JSON"})
    except Exception as e:
      _json(self, 500, {"error": str(e)})
