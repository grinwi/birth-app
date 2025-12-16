function forwardHeaders(req: Request) {
  const headers = new Headers();
  const toCopy = ['accept', 'content-type', 'authorization', 'cookie', 'x-forwarded-for'];
  for (const k of toCopy) {
    const v = req.headers.get(k);
    if (v) headers.set(k, v);
  }
  return headers;
}

async function proxy(method: 'PUT' | 'DELETE', req: Request, index: string) {
  const url = new URL(req.url);
  // Bypass rewrite indirection and hit the Python function directly to avoid 405s on some hosts
  const target = `${url.origin}/api/people_index.py?index=${encodeURIComponent(index)}`;
  const reqHeaders = forwardHeaders(req);
  reqHeaders.set('X-HTTP-Method-Override', method);
  const init: RequestInit = {
    method: 'POST',
    headers: reqHeaders,
    cache: 'no-store',
  };
  if (method === 'PUT') {
    init.body = await req.text();
  }

  const res = await fetch(target, init);
  const body = await res.text();
  const outBody = body && body.length ? body : (!res.ok ? JSON.stringify({ ok: false, status: res.status, error: 'empty_error_body_from_backend' }) : body);

  const respHeaders = new Headers();
  respHeaders.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
  return new Response(outBody, { status: res.status, headers: respHeaders });
}
 
export async function OPTIONS() {
  return new Response(null, { status: 204 });
}
 
export async function PUT(req: Request, ctx: { params: { index: string } }) {
  try {
    return await proxy('PUT', req, ctx.params.index);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_index_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}

export async function DELETE(req: Request, ctx: { params: { index: string } }) {
  try {
    return await proxy('DELETE', req, ctx.params.index);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_index_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}
