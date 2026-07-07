import { getStore } from "@netlify/blobs";

const WORKBOOK_KEY = "tongji_summary_current.xlsx";
const MAX_WORKBOOK_BYTES = 20 * 1024 * 1024;
const WORKBOOK_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function requireUploadToken(request) {
  const uploadToken = process.env.DASHBOARD_SYNC_TOKEN || process.env.REPORT_UPLOAD_TOKEN;
  if (!uploadToken) {
    return Response.json({ error: "DASHBOARD_SYNC_TOKEN is not configured" }, { status: 500 });
  }
  if (request.headers.get("authorization") !== `Bearer ${uploadToken}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}

export default async function dashboardWorkbook(request) {
  const store = getStore({ name: "dashboard-workbook", consistency: "strong" });

  if (request.method === "GET" || request.method === "HEAD") {
    const data = await store.get(WORKBOOK_KEY, { type: "arrayBuffer" });
    if (data === null) {
      return Response.redirect(new URL("/downloads/tongji_summary_current.xlsx", request.url), 302);
    }
    return new Response(request.method === "HEAD" ? null : data, {
      headers: {
        "Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="tongji_summary_current.xlsx"',
        "Content-Length": String(data.byteLength),
        "Content-Type": WORKBOOK_TYPE,
      },
    });
  }

  if (request.method === "POST") {
    const tokenError = requireUploadToken(request);
    if (tokenError) return tokenError;
    if (Number(request.headers.get("content-length") || 0) > MAX_WORKBOOK_BYTES) {
      return Response.json({ error: "Workbook is too large" }, { status: 413 });
    }
    const workbook = await request.blob();
    if (workbook.size > MAX_WORKBOOK_BYTES) {
      return Response.json({ error: "Workbook is too large" }, { status: 413 });
    }
    await store.set(WORKBOOK_KEY, workbook);
    return Response.json({ ok: true, size: workbook.size });
  }

  return new Response(null, { status: 405, headers: { Allow: "GET, HEAD, POST" } });
}
