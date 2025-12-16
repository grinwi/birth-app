function forwardHeaders(req: Request) {
  const headers = new Headers();
  const toCopy = ['accept', 'content-type', 'authorization', 'cookie', 'x-forwarded-for'];
  for (const k of toCopy) {
    const v = req.headers.get(k);
    if (v) headers.set(k, v);
  }
  return headers;
}

async function proxy(method: 'GET' | 'POST', req: Request) {
  const url = new URL(req.url);
  const target = `${url.origin}/api/json.py`;
  const init: RequestInit = {
    method,
    headers: forwardHeaders(req),
    cache: 'no-store',
  };
  if (method === 'POST') {
    init.body = await req.text();
  }
  const res = await fetch(target, init);
  const body = await res.text();
  const outBody = body && body.length ? body : (!res.ok ? JSON.stringify({ ok: false, status: res.status, error: 'empty_error_body_from_backend' }) : body);

  const headers = new Headers();
  headers.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
  return new Response(outBody, { status: res.status, headers });
}

export async function OPTIONS() {
  return new Response(null, { status: 204 });
}

export async function HEAD(req: Request) {
  try {
    return await proxy('GET', req);
  } catch {
    return new Response(null, { status: 500 });
  }
}

export async function GET(req: Request) {
  try {
    return await proxy('GET', req);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'json_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}

export async function POST(req: Request) {
  try {
    return await proxy('POST', req);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'json_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}
