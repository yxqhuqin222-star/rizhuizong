import { getStore } from "@netlify/blobs";

const STATE_KEY = "current.json";
const MAX_STATE_BYTES = 2 * 1024 * 1024;

function unauthorized() {
  return Response.json({ error: "Unauthorized" }, { status: 401 });
}

function requireUploadToken(request) {
  const uploadToken = process.env.DASHBOARD_SYNC_TOKEN || process.env.REPORT_UPLOAD_TOKEN;
  if (!uploadToken) {
    return Response.json({ error: "DASHBOARD_SYNC_TOKEN is not configured" }, { status: 500 });
  }
  if (request.headers.get("authorization") !== `Bearer ${uploadToken}`) {
    return unauthorized();
  }
  return null;
}

async function fallbackStaticState(request) {
  const url = new URL(request.url);
  const fallbackUrl = new URL("/api/state-static.json", url.origin);
  const response = await fetch(fallbackUrl, { headers: { accept: "application/json" } });
  if (!response.ok) {
    return Response.json({ error: "No dashboard state has been published" }, { status: 404 });
  }
  return new Response(request.method === "HEAD" ? null : await response.arrayBuffer(), {
    status: 200,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

export default async function dashboardState(request) {
  const store = getStore({ name: "dashboard-state", consistency: "strong" });

  if (request.method === "GET" || request.method === "HEAD") {
    const data = await store.get(STATE_KEY, { type: "arrayBuffer" });
    if (data === null) {
      return fallbackStaticState(request);
    }
    return new Response(request.method === "HEAD" ? null : data, {
      headers: {
        "Cache-Control": "no-store",
        "Content-Length": String(data.byteLength),
        "Content-Type": "application/json; charset=utf-8",
      },
    });
  }

  if (request.method === "POST") {
    const tokenError = requireUploadToken(request);
    if (tokenError) return tokenError;
    if (!request.headers.get("content-type")?.startsWith("application/json")) {
      return Response.json({ error: "Expected application/json" }, { status: 415 });
    }
    if (Number(request.headers.get("content-length") || 0) > MAX_STATE_BYTES) {
      return Response.json({ error: "State payload is too large" }, { status: 413 });
    }

    const text = await request.text();
    if (new TextEncoder().encode(text).byteLength > MAX_STATE_BYTES) {
      return Response.json({ error: "State payload is too large" }, { status: 413 });
    }
    let state;
    try {
      state = JSON.parse(text);
    } catch {
      return Response.json({ error: "Invalid JSON" }, { status: 400 });
    }
    if (!Array.isArray(state.summary) || !Array.isArray(state.latestSummary) || !state.metrics) {
      return Response.json({ error: "Invalid dashboard state" }, { status: 400 });
    }

    await store.set(STATE_KEY, JSON.stringify(state));
    return Response.json({ ok: true, syncedAt: state.syncedAt || null });
  }

  return new Response(null, { status: 405, headers: { Allow: "GET, HEAD, POST" } });
}
