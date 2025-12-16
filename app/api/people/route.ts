
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
  const target = `${url.origin}/api-py/people${url.search}`;
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

  // Mirror status and content-type from backend
  const headers = new Headers();
  headers.set('content-type', res.headers.get('content-type') || 'application/json; charset=utf-8');
  return new Response(body, { status: res.status, headers });
}

export async function OPTIONS() {
  return new Response(null, { status: 204 });
}

export async function HEAD(req: Request) {
  try {
    // Mirror GET but without forcing body consumption
    return await proxy('GET', req);
  } catch {
    return new Response(null, { status: 500 });
  }
}

export async function GET(req: Request) {
  try {
    return await proxy('GET', req);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}

export async function POST(req: Request) {
  try {
    return await proxy('POST', req);
  } catch (e: any) {
    return new Response(JSON.stringify({ ok: false, error: 'people_proxy_failed', detail: e?.message || String(e) }), {
      status: 500,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
}
