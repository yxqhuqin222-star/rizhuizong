import { getStore } from "@netlify/blobs";

const REPORT_TYPES = new Set(["primary", "middle", "high", "lec1"]);
const REPORT_KEY_PATTERN = /^(primary|middle|high|lec1)\/\d+-[0-9a-f-]+\.png$/;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

export default async function reportImage(request) {
  const url = new URL(request.url);

  if (request.method === "POST") {
    const uploadToken = process.env.REPORT_UPLOAD_TOKEN;
    const providedToken = request.headers.get("authorization");
    if (!uploadToken) {
      return Response.json({ error: "REPORT_UPLOAD_TOKEN is not configured" }, { status: 500 });
    }
    if (providedToken !== `Bearer ${uploadToken}`) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }

    const dept = url.searchParams.get("dept");
    if (!REPORT_TYPES.has(dept)) {
      return Response.json({ error: "Unknown report type" }, { status: 400 });
    }
    if (request.headers.get("content-type") !== "image/png") {
      return Response.json({ error: "Expected image/png" }, { status: 415 });
    }
    if (Number(request.headers.get("content-length") || 0) > MAX_IMAGE_BYTES) {
      return Response.json({ error: "Image is too large" }, { status: 413 });
    }

    const image = await request.blob();
    if (image.size > MAX_IMAGE_BYTES) {
      return Response.json({ error: "Image is too large" }, { status: 413 });
    }
    const key = `${dept}/${Date.now()}-${crypto.randomUUID()}.png`;
    const store = getStore({ name: "report-images", consistency: "strong" });
    await store.set(key, image);

    const imageUrl = new URL("/.netlify/functions/report-image", url.origin);
    imageUrl.searchParams.set("key", key);
    return Response.json({ url: imageUrl.toString() });
  }

  if (request.method === "GET" || request.method === "HEAD") {
    const key = url.searchParams.get("key");
    if (!key) {
      return Response.json({ error: "Missing key" }, { status: 400 });
    }
    if (!REPORT_KEY_PATTERN.test(key)) {
      return Response.json({ error: "Invalid key" }, { status: 400 });
    }

    const store = getStore({ name: "report-images", consistency: "strong" });
    const image = await store.get(key, { type: "arrayBuffer" });
    if (image === null) {
      return Response.json({ error: "Not found" }, { status: 404 });
    }

    const headers = {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Length": String(image.byteLength),
      "Content-Type": "image/png",
    };
    return new Response(request.method === "HEAD" ? null : image, { headers });
  }

  return new Response(null, { status: 405, headers: { Allow: "GET, HEAD, POST" } });
}
