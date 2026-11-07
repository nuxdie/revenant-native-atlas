type AtlasEnv = { BUCKET: R2Bucket; ATLAS_UPLOAD_KEY?: string };
type Tile = { offset: number; length: number; sha256: string };
type TileIndex = { pack: string; tiles: Record<string, Tile> };
const indexes = new Map<string, TileIndex>();
const MAX_PART = 20 * 1024 * 1024;
const keyPattern = /^(catalog\.json|retail-preview-catalog\.json|releases\/[a-z0-9-]{1,48}\/level-\d+\/(tiles\.(pack|json)|overview\.jpg|full-resolution\.(png|zip|tif)|validation\.json))$/;
const immutable = "public, max-age=31536000, immutable";

function json(value: unknown, status = 200) {
  return Response.json(value, { status, headers: { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
}
function sameSecret(a: string, b?: string) {
  if (!b || a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}
function mime(key: string) {
  return key.endsWith(".png") ? "image/png" : key.endsWith(".tif") ? "image/tiff" : key.endsWith(".jpg") ? "image/jpeg" : key.endsWith(".zip") ? "application/zip" : key.endsWith(".json") ? "application/json" : "application/octet-stream";
}
async function smallJson(request: Request) {
  const text = await request.text();
  if (text.length > 64 * 1024) throw new Error("JSON request too large");
  return JSON.parse(text);
}
async function upload(request: Request, env: AtlasEnv, url: URL) {
  if (!sameSecret(request.headers.get("Authorization")?.replace(/^Bearer /, "") || "", env.ATLAS_UPLOAD_KEY)) return json({ error: "Unauthorized" }, 401);
  const key = url.searchParams.get("key") || "";
  if (!keyPattern.test(key)) return json({ error: "Invalid object key" }, 400);
  const action = url.searchParams.get("action");
  if (action === "delete-object" && request.method === "POST") {
    if (!key.startsWith("releases/")) return json({ error: "Only immutable release objects can be removed" }, 400);
    await env.BUCKET.delete(key);
    return json({ deleted: key });
  }
  if (action === "delete-zip" && request.method === "POST") {
    if (!key.endsWith("/full-resolution.zip")) return json({ error: "Only obsolete map ZIPs can be removed" }, 400);
    await env.BUCKET.delete(key);
    return json({ deleted: key });
  }
  if (action === "read" && request.method === "GET") return await file(request, env, key);
  if (action === "head" && request.method === "GET") {
    const object = await env.BUCKET.head(key);
    return object ? json({ size: object.size, sha256: object.customMetadata?.sha256 }) : json({ error: "Not found" }, 404);
  }
  if (action === "start" && request.method === "POST") {
    const data = await smallJson(request);
    if (!Number.isSafeInteger(data.size) || data.size < 1 || data.size > 10 * 1024 ** 3 || !/^[a-f0-9]{64}$/.test(data.sha256)) return json({ error: "Invalid file metadata" }, 400);
    const multipart = await env.BUCKET.createMultipartUpload(key, { httpMetadata: { contentType: mime(key) }, customMetadata: { sha256: data.sha256, bytes: String(data.size) } });
    return json({ uploadId: multipart.uploadId });
  }
  if (action === "part" && request.method === "PUT") {
    const size = Number(request.headers.get("Content-Length"));
    const part = Number(url.searchParams.get("part"));
    const id = url.searchParams.get("id");
    if (!id || !Number.isSafeInteger(part) || part < 1 || part > 10000 || !Number.isSafeInteger(size) || size < 1 || size > MAX_PART || !request.body) return json({ error: "Invalid upload part" }, 400);
    const result = await env.BUCKET.resumeMultipartUpload(key, id).uploadPart(part, request.body);
    return json(result);
  }
  if (action === "complete" && request.method === "POST") {
    const data = await smallJson(request);const id = url.searchParams.get("id");
    if (!id || !Array.isArray(data.parts) || !data.parts.length || data.parts.some((p: {partNumber:number;etag:string}, i: number) => p.partNumber !== i + 1 || typeof p.etag !== "string")) return json({ error: "Invalid completion" }, 400);
    const result = await env.BUCKET.resumeMultipartUpload(key, id).complete(data.parts);
    return json({ size: result.size, sha256: result.customMetadata?.sha256 });
  }
  if (action === "put" && request.method === "PUT") {
    const size = Number(request.headers.get("Content-Length"));const sha = request.headers.get("X-Content-SHA256") || "";
    if (!Number.isSafeInteger(size) || size < 1 || size > MAX_PART || !/^[a-f0-9]{64}$/.test(sha) || !request.body) return json({ error: "Invalid file" }, 400);
    const result = await env.BUCKET.put(key, request.body, { httpMetadata: { contentType: mime(key) }, customMetadata: { sha256: sha, bytes: String(size) } });
    return json({ size: result?.size, sha256: result?.customMetadata?.sha256 });
  }
  return json({ error: "Unsupported upload operation" }, 405);
}

export function parseRange(value: string | null, size: number): {offset:number;length:number} | null | false {
  if (!value) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(value);
  if (!match || (!match[1] && !match[2])) return false;
  let start: number, end: number;
  if (!match[1]) { const count = Number(match[2]);if (count < 1) return false;start = Math.max(0, size - count);end = size - 1; }
  else { start = Number(match[1]);end = match[2] ? Math.min(size - 1, Number(match[2])) : size - 1; }
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || start >= size || end < start) return false;
  return { offset: start, length: end - start + 1 };
}

async function file(request: Request, env: AtlasEnv, key: string, attachment: boolean | string = false) {
  const head = await env.BUCKET.head(key);
  if (!head) return json({ error: "Map file not found" }, 404);
  const headers = new Headers({ "Content-Type": mime(key), "Cache-Control": key === "catalog.json" || key === "retail-preview-catalog.json" ? "public, max-age=30" : immutable, "ETag": head.httpEtag, "Accept-Ranges": "bytes", "X-Content-Type-Options": "nosniff" });
  if (head.customMetadata?.sha256) headers.set("X-Content-SHA256", head.customMetadata.sha256);
  if (request.headers.get("If-None-Match") === head.httpEtag) return new Response(null, { status: 304, headers });
  if (attachment) headers.set("Content-Disposition", `attachment; filename="${typeof attachment === 'string' ? attachment : `revenant-${key.split("/").slice(-2).join("-")}`}"`);
  const range = parseRange(request.headers.get("Range"), head.size);
  if (range === false) { headers.set("Content-Range", `bytes */${head.size}`);return new Response(null, { status: 416, headers }); }
  headers.set("Content-Length", String(range ? range.length : head.size));
  if (range) headers.set("Content-Range", `bytes ${range.offset}-${range.offset + range.length - 1}/${head.size}`);
  const object = request.method === "HEAD" ? null : await env.BUCKET.get(key, range ? { range } : undefined);
  return new Response(object?.body || null, { status: range ? 206 : 200, headers });
}

export async function handleAtlas(request: Request, env: AtlasEnv): Promise<Response | null> {
  const url = new URL(request.url);
  if (!url.pathname.startsWith("/api/")) return null;
  if (!env.BUCKET) return json({ error: "Map storage is being prepared" }, 503);
  try {
    if (url.pathname === "/api/upload") return await upload(request, env, url);
    if (!["GET", "HEAD"].includes(request.method)) return json({ error: "Read-only endpoint" }, 405);
    if (url.pathname === "/api/catalog") return await file(request, env, url.searchParams.get('dataset')==='retail'?'retail-preview-catalog.json':'catalog.json');
    const revision = url.searchParams.get("revision") || "";const level = url.searchParams.get("level") || "";
    if (!/^[a-z0-9-]{1,48}$/.test(revision) || !/^\d{1,3}$/.test(level)) return json({ error: "Invalid map" }, 400);
    const prefix = `releases/${revision}/level-${level}/`;
    if (url.pathname === "/api/file") {
      const name = url.searchParams.get("name") || "";
      if (!/^(overview\.jpg|full-resolution\.(png|tif))$/.test(name)) return json({ error: "Invalid map file" }, 404);
      const variant = url.searchParams.get("variant") || "";
      if (variant && !/^(day|night|twilight|fixed)$/.test(variant)) return json({error:"Invalid lighting state"},400);
      const edition = url.searchParams.get("dataset")=== "retail" ? "retail-1.22l" : url.searchParams.get("dataset")=== "july" ? "july-1999" : "";
      const attachment = name === "overview.jpg" ? false : `revenant-${edition ? edition+'-' : ''}level-${level}${variant ? `-${variant}` : ''}.${name.endsWith('.tif') ? 'tif' : 'png'}`;
      return await file(request, env, prefix + name, attachment);
    }
    if (url.pathname === "/api/tile") {
      const x = url.searchParams.get("x") || "";const y = url.searchParams.get("y") || "";
      if (!/^\d{1,4}$/.test(x) || !/^\d{1,4}$/.test(y)) return json({ error: "Invalid tile" }, 400);
      let index = indexes.get(prefix);
      if (!index) {
        const object = await env.BUCKET.get(prefix + "tiles.json");
        if (!object) return json({ error: "Map not found" }, 404);
        index = await object.json<TileIndex>();indexes.set(prefix, index);
        if (indexes.size > 66) indexes.delete(indexes.keys().next().value!);
      }
      const tile = index.tiles[`${x}_${y}`];
      if (!tile) return json({ error: "Tile not found" }, 404);
      const headers = new Headers({ "Content-Type": "image/png", "Content-Length": String(tile.length), "Cache-Control": immutable, "ETag": `"${tile.sha256}"`, "X-Content-Type-Options": "nosniff" });
      if (request.headers.get("If-None-Match") === `"${tile.sha256}"`) return new Response(null, { status: 304, headers });
      const object = request.method === "HEAD" ? null : await env.BUCKET.get(prefix + "tiles.pack", { range: { offset: tile.offset, length: tile.length } });
      return new Response(object?.body || null, { headers });
    }
    return json({ error: "Not found" }, 404);
  } catch (error) {
    console.error("Atlas storage request failed", String(error));
    return json({ error: "Map storage operation failed" }, 500);
  }
}
