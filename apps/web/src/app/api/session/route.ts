import { NextResponse } from "next/server";
import { boundedBody, configuredBackend, trustedWriteOrigin } from "@/lib/backendProxyPolicy";
export const maxDuration = 120;

function allowed(request: Request): boolean {
  return process.env.FACTORYMIND_DEPLOYMENT_TARGET === "render" &&
    trustedWriteOrigin(request.headers.get("origin"), process.env.FACTORYMIND_WEB_ORIGIN ?? "");
}
export async function POST(request: Request) {
  if (!allowed(request)) return Response.json({ detail: "Sign-in origin is not authorized" }, { status: 403 });
  const backend = configuredBackend(process.env.FACTORYMIND_BACKEND_URL ?? "");
  const supabase = configuredBackend(process.env.FACTORYMIND_SUPABASE_URL ?? "");
  const apiKey = process.env.FACTORYMIND_SUPABASE_ANON_KEY;
  if (!backend || !supabase || !apiKey) return Response.json({ detail: "Sign-in is not configured" }, { status: 503 });
  const body = await boundedBody(request, 4096);
  if (!body) return Response.json({ detail: "Invalid sign-in request" }, { status: 413 });
  try {
    const input: unknown = JSON.parse(new TextDecoder().decode(body));
    if (!input || typeof input !== "object" || !("email" in input) || !("password" in input) || typeof input.email !== "string" || typeof input.password !== "string") return Response.json({ detail: "Email and password are required" }, { status: 400 });
    const response = await fetch(`${supabase.origin}/auth/v1/token?grant_type=password`, { method: "POST", headers: { apikey: apiKey, "Content-Type": "application/json" }, body: JSON.stringify({ email: input.email, password: input.password }), cache: "no-store", redirect: "error", signal: AbortSignal.timeout(15_000) });
    if (!response.ok) return Response.json({ detail: "Sign-in failed. Check credentials or Auth rate limits." }, { status: 401 });
    const session = await response.json() as { access_token?: string; expires_in?: number };
    if (!session.access_token || !/^[A-Za-z0-9_.-]{20,16000}$/.test(session.access_token)) throw new Error("Invalid session");
    const access = await fetch(`${backend.origin}/api/auth/session`, { headers: { Authorization: `Bearer ${session.access_token}` }, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(75_000) });
    if (!access.ok) return Response.json({ detail: "This account cannot access the demo workspace" }, { status: 403 });
    const result = NextResponse.json({ authenticated: true });
    result.cookies.set("fm_session", session.access_token, { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: Math.min(Math.max(1, session.expires_in ?? 3600), 3600) });
    result.headers.set("Cache-Control", "private, no-store");
    return result;
  } catch {
    return Response.json({ detail: "Sign-in service unavailable; try again after the backend wakes" }, { status: 503 });
  }
}
export function DELETE(request: Request) {
  if (!allowed(request)) return Response.json({ detail: "Sign-out origin is not authorized" }, { status: 403 });
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set("fm_session", "", { httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 0 });
  return response;
}
