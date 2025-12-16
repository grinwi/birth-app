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
  const target = `${url.origin}/api-py/people/${encodeURIComponent(index)}`;
  const init: RequestInit = {
    method,
    headers: forwardHeaders(req),
    cache: 'no-store',
  };
  if (method === 'PUT') {
    init.body = await req.text();
  }

  const res = await fetch(target, init);
  const body = await res.text();

  const headers = new Headers();
  headers.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
  return new Response(body, { status: res.status, headers });
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
