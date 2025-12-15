import json
from http.server import BaseHTTPRequestHandler

from _auth import (
  authenticate_user,
  bootstrap_admin_if_empty,
  create_jwt,
  build_auth_cookie,
)

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
  # POST {username, password}
  def do_POST(self):
    try:
      length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(length) if length > 0 else b"{}"
      payload = json.loads(body.decode("utf-8") or "{}")
      username = (payload.get("username") or "").strip()
      password = (payload.get("password") or "").strip()

      if not username or not password:
        _json(self, 400, {"error": "username and password required"})
        return

      # Bootstrap first admin if store empty and ADMIN_INITIAL_PASSWORD configured
      if username == "admin":
        try:
          if bootstrap_admin_if_empty(username, password):
            token = create_jwt(sub=username, role="admin")
            cookie = build_auth_cookie(token)
            _json(self, 200, {"ok": True, "role": "admin"}, set_cookie=cookie)
            return
        except Exception:
          # ignore bootstrap errors, fallback to normal auth
          pass

      ok, sub, role = authenticate_user(username, password)
      if not ok:
        _json(self, 401, {"error": "Invalid credentials"})
        return

      token = create_jwt(sub=sub, role=role or "user")
      cookie = build_auth_cookie(token)
      _json(self, 200, {"ok": True, "role": role or "user"}, set_cookie=cookie)
    except json.JSONDecodeError:
      _json(self, 400, {"error": "Invalid JSON"})
    except Exception as e:
      _json(self, 500, {"error": str(e)})
