"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
export default function PortableAccess() {
  const router = useRouter();
  const [error, setError] = useState("");
  async function signOut() {
    try {
      const response = await fetch("/api/session", { method: "DELETE" });
      if (!response.ok) throw new Error("Sign-out failed");
      router.replace("/login"); router.refresh();
    } catch { setError("Sign-out could not be confirmed. Check connectivity and retry."); }
  }
  return <div className="flex flex-wrap items-center justify-end gap-4 border-b border-line px-5 py-2 text-xs text-slate-400"><span>Invited demo workspace · writes restricted to presenters</span><Link href="/login" className="underline">Sign in</Link><button onClick={signOut} className="underline">Sign out</button>{error && <span role="alert">{error}</span>}</div>;
}
