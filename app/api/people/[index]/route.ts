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
  const reqHeaders = forwardHeaders(req);
  reqHeaders.set('X-HTTP-Method-Override', method);
  const base = url.origin;
  const targets = [
    `${base}/api/people_index.py?index=${encodeURIComponent(index)}&method=${encodeURIComponent(method)}`,
    `${base}/api-py/people/${encodeURIComponent(index)}?method=${encodeURIComponent(method)}`,
    `${base}/api-py/people/${encodeURIComponent(index)}`
  ];
  const initBase: RequestInit = {
    method: 'POST',
    headers: reqHeaders,
    cache: 'no-store',
  };
  if (method === 'PUT') {
    initBase.body = await req.text();
  }

  let lastRes: Response | null = null;
  for (const t of targets) {
    const res = await fetch(t, initBase);
    lastRes = res;
    // Treat 404/405 as "try next target", return immediately for all other statuses
    if (res.status !== 404 && res.status !== 405) {
      const body = await res.text();
      const outBody = body && body.length ? body : (!res.ok ? JSON.stringify({ ok: false, status: res.status, error: 'empty_error_body_from_backend' }) : body);
      const respHeaders = new Headers();
      respHeaders.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
      return new Response(outBody, { status: res.status, headers: respHeaders });
    }
  }

  // If all attempts resulted in 404/405, return the last one with a meaningful body
  if (lastRes) {
    const body = await lastRes.text();
    const outBody = body && body.length ? body : JSON.stringify({ ok: false, status: lastRes.status, error: 'all_targets_failed' });
    const respHeaders = new Headers();
    respHeaders.set('content-type', lastRes.headers.get('content-type') || 'application/json; charset=utf-8');
    return new Response(outBody, { status: lastRes.status, headers: respHeaders });
  }

  // Should not happen, but guard just in case
  return new Response(JSON.stringify({ ok: false, error: 'no_response' }), {
    status: 502,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
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
