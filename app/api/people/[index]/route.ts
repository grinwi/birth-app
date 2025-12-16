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

  const tried: Array<{ url: string; status: number; body: string }> = [];
  for (const t of targets) {
    let res: Response;
    try {
      res = await fetch(t, initBase);
    } catch (e: any) {
      tried.push({ url: t, status: 0, body: `network_error: ${e?.message || String(e)}` });
      continue;
    }
    const text = await res.text();
    if (res.status !== 404 && res.status !== 405) {
      const outBody = text && text.length ? text : (!res.ok ? JSON.stringify({ ok: false, status: res.status, error: 'empty_error_body_from_backend', target: t }) : text);
      const respHeaders = new Headers();
      respHeaders.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
      return new Response(outBody, { status: res.status, headers: respHeaders });
    }
    tried.push({ url: t, status: res.status, body: (text || '').slice(0, 400) });
  }

  // All attempts were 404/405 or failed: return diagnostics to help identify which target is blocked
  const diag = {
    ok: false,
    error: 'all_targets_failed',
    note: 'Hosts may block PUT/DELETE or strip override hints. We tried multiple targets via POST with X-HTTP-Method-Override.',
    tried,
  };
  return new Response(JSON.stringify(diag), {
    status: tried.length ? (tried[tried.length - 1].status || 502) : 502,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}
 
export async function OPTIONS() {
  return new Response(null, { status: 204 });
}

/**
 * Support GET /api/people/:index by fetching the full list and returning the element.
 * This is a convenience so clients can retrieve a single row by index.
 */
export async function GET(req: Request, ctx: { params: { index: string } }) {
  try {
    const url = new URL(req.url);
    const base = url.origin;
    const listRes = await fetch(`${base}/api/people.py`, { method: 'GET', cache: 'no-store' });
    const text = await listRes.text();
    if (!listRes.ok) {
      const respHeaders = new Headers();
      respHeaders.set('content-type', listRes.headers.get('content-type') || 'application/json; charset=utf-8');
      const outBody = text && text.length ? text : JSON.stringify({ ok: false, status: listRes.status, error: 'failed_to_fetch_list' });
      return new Response(outBody, { status: listRes.status, headers: respHeaders });
    }
    let payload: any = {};
    try { payload = JSON.parse(text); } catch {}
    const rows = Array.isArray(payload?.data) ? payload.data : [];
    const idx = parseInt(ctx.params.index, 10);
    if (!Number.isFinite(idx) || idx < 0 || idx >= rows.length) {
      return new Response(JSON.stringify({ ok: false, error: 'Index out of range', index: idx, count: rows.length }), {
        status: 404,
        headers: { 'content-type': 'application/json; charset=utf-8' },
      });
    }
    return new Response(JSON.stringify({ ok: true, index: idx, data: rows[idx] }), {
      status: 200,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_index_get_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}

export async function POST(req: Request, ctx: { params: { index: string } }) {
  try {
    const url = new URL(req.url);
    const override = (req.headers.get('x-http-method-override') || url.searchParams.get('method') || 'PUT').toUpperCase();
    const method = override === 'DELETE' ? 'DELETE' : 'PUT';
    // Delegate to the same proxy using the inferred method
    return await proxy(method as 'PUT' | 'DELETE', req, ctx.params.index);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_index_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
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
