function forwardHeaders(req: Request) {
  const headers = new Headers();
  const toCopy = ['accept', 'content-type', 'authorization', 'cookie', 'x-forwarded-for'];
  for (const k of toCopy) {
    const v = req.headers.get(k);
    if (v) headers.set(k, v);
  }
  return headers;
}

function parseIndexFromSlug(slug: string[] | undefined): number | null {
  if (!slug || !slug.length) return null;
  const s = slug[0];
  const idx = Number.parseInt(s, 10);
  return Number.isFinite(idx) && idx >= 0 ? idx : null;
}

async function proxy(method: 'PUT' | 'DELETE', req: Request, index: number) {
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

  // All attempts failed, return diagnostics.
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
 * GET /api/people/[...slug] => treat slug[0] as zero-based index; returns that element
 */
export async function GET(req: Request, ctx: { params: { slug?: string[] } }) {
  try {
    const idx = parseIndexFromSlug(ctx.params.slug);
    if (idx == null) {
      return new Response(JSON.stringify({ ok: false, error: 'Invalid index' }), {
        status: 400,
        headers: { 'content-type': 'application/json; charset=utf-8' },
      });
    }
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
    if (idx < 0 || idx >= rows.length) {
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

/**
 * POST /api/people/[...slug] with X-HTTP-Method-Override: PUT|DELETE
 */
export async function POST(req: Request, ctx: { params: { slug?: string[] } }) {
  try {
    const idx = parseIndexFromSlug(ctx.params.slug);
    if (idx == null) {
      return new Response(JSON.stringify({ ok: false, error: 'Invalid index' }), {
        status: 400,
        headers: { 'content-type': 'application/json; charset=utf-8' },
      });
    }
    const url = new URL(req.url);
    const override = (req.headers.get('x-http-method-override') || url.searchParams.get('method') || 'PUT').toUpperCase();
    const method = override === 'DELETE' ? 'DELETE' : 'PUT';
    return await proxy(method as 'PUT' | 'DELETE', req, idx);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_index_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}

/**
 * Direct PUT/DELETE support (will call through proxy with fallback targets)
 */
export async function PUT(req: Request, ctx: { params: { slug?: string[] } }) {
  const idx = parseIndexFromSlug(ctx.params.slug);
  if (idx == null) {
    return new Response(JSON.stringify({ ok: false, error: 'Invalid index' }), {
      status: 400,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
  return proxy('PUT', req, idx);
}

export async function DELETE(req: Request, ctx: { params: { slug?: string[] } }) {
  const idx = parseIndexFromSlug(ctx.params.slug);
  if (idx == null) {
    return new Response(JSON.stringify({ ok: false, error: 'Invalid index' }), {
      status: 400,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
  return proxy('DELETE', req, idx);
}
