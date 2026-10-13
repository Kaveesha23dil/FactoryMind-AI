import { GoogleAuth } from "google-auth-library";
import { allowedBackendPath, configuredBackend, trustedWriteOrigin, boundedBody } from "@/lib/backendProxyPolicy";

const auth = new GoogleAuth();
const LIMIT = 6 * 1024 * 1024;

async function forward(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const backend = process.env.FACTORYMIND_BACKEND_URL;
  if (!backend) return Response.json({ detail: "Backend connection is not configured" }, { status: 503 });
  const base = configuredBackend(backend);
  if (!base) {
    return Response.json({ detail: "Invalid backend configuration" }, { status: 503 });
  }
  const { path } = await context.params;
  if (!allowedBackendPath(path)) {
    return Response.json({ detail: "Backend route is not allowed" }, { status: 403 });
  }
  const write = request.method !== "GET" && request.method !== "HEAD";
  if (write) {
    const origin = request.headers.get("origin");
    const trusted = process.env.FACTORYMIND_WEB_ORIGIN ?? new URL(request.url).origin;
    if (!trustedWriteOrigin(origin, trusted)) return Response.json({ detail: "Untrusted request origin" }, { status: 403 });
  }
  const body = write ? await boundedBody(request, LIMIT) : undefined;
  if (body === null) {
    return Response.json({ detail: "Upload exceeds proxy limit" }, { status: 413 });
  }
  try {
    const client = await auth.getIdTokenClient(base.origin);
    const token = await client.idTokenProvider.fetchIdToken(base.origin);
    const headers = new Headers();
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("X-Serverless-Authorization", `Bearer ${token}`);
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    const incoming = new URL(request.url);
    const target = new URL(`/${path.join("/")}`, base);
    target.search = incoming.search;
    const upstream = await fetch(target, {
      method: request.method, headers, body,
      redirect: "error", cache: "no-store", signal: AbortSignal.timeout(895_000),
    });
    const responseHeaders = new Headers({ "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "retry-after"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: "Private backend is unavailable or service authorization failed" }, { status: 502 });
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
