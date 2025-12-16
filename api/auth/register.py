import json
from http.server import BaseHTTPRequestHandler

from .._auth import consume_invite, create_user, create_jwt, build_auth_cookie

def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict, set_cookie: str | None = None):
  data = json.dumps(payload).encode("utf-8")
  handler.send_response(status)
  handler.send_header("Content-Type", "application/json; charset=utf-8")
  handler.send_header("Content-Length", str(len(data)))
  if set_cookie:
    handler.send_header("Set-Cookie", set_cookie)
  handler.end_headers()
  handler.wfile.write(data)

class handler(BaseHTTPRequestHandler):
  # POST {"token": "...", "username": "...", "password": "..."}
  def do_POST(self):
    try:
      length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(length) if length > 0 else b"{}"
      payload = json.loads(body.decode("utf-8") or "{}")

      token = (payload.get("token") or "").strip()
      username = (payload.get("username") or "").strip()
      password = (payload.get("password") or "").strip()

      if not token or not username or not password:
        _json(self, 400, {"error": "token, username and password are required"})
        return

      inv = consume_invite(token)
      if inv is None:
        _json(self, 400, {"error": "Invalid or expired invite token"})
        return

      role = (inv.get("role") or "user").strip().lower()
      if role not in ("user", "admin"):
        role = "user"

      # Create user
      create_user(username, password, role=role)

      # Log them in by setting cookie
      jwt = create_jwt(sub=username, role=role)
      cookie = build_auth_cookie(jwt)

      _json(self, 201, {"ok": True, "role": role}, set_cookie=cookie)
    except json.JSONDecodeError:
      _json(self, 400, {"error": "Invalid JSON"})
    except Exception as e:
      _json(self, 500, {"error": str(e)})
