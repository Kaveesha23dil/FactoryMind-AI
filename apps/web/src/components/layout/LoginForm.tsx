"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
export default function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
      if (!response.ok) throw new Error((await response.json() as { detail: string }).detail);
      router.replace("/overview"); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-in failed"); setBusy(false); }
  }
  return <main className="mx-auto max-w-md p-8"><h1 className="text-2xl font-semibold">FactoryMind AI</h1><p className="my-4 text-sm text-slate-400">Sign in with your invited Supabase account. Approved demo members share one workspace; presenter write access is granted separately.</p><form className="space-y-4" onSubmit={submit}><label className="block text-sm">Email<input className="mt-2 block w-full rounded border border-line bg-surface p-3" name="email" type="email" autoComplete="username" required /></label><label className="block text-sm">Password<input className="mt-2 block w-full rounded border border-line bg-surface p-3" name="password" type="password" autoComplete="current-password" required /></label>{error && <p role="alert" className="text-sm text-danger">{error}</p>}<button className="rounded bg-accent px-5 py-3 text-sm text-white" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button></form><p className="mt-5 text-xs text-slate-500">A sleeping backend may take about a minute to wake. Sessions expire; sign in again if prompted.</p></main>;
}
