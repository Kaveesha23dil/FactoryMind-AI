"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { SubmissionOverview } from "@/types/submission";

export default function OperationalOverview() {
  const [data, setData] = useState<SubmissionOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let stale = false;
    void apiFetch<SubmissionOverview>("/api/submission/overview").then(value => { if (!stale) setData(value); })
      .catch(reason => { if (!stale) setError(reason instanceof Error ? reason.message : "Operational data unavailable"); });
    return () => { stale = true; };
  }, []);
  return <section className="space-y-4 rounded-lg border border-line bg-surface p-5" aria-label="Investigation operations">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-semibold text-white">Investigation operations</h2><Link className="text-sm text-cyan-accent underline" href="/demo">Open guided saved demo →</Link></div>
    <p className="text-xs text-slate-400">Synthetic benchmark observations and persisted application records. These are not factory uptime or live telemetry metrics.</p>
    {error && <p role="alert" className="text-sm text-warning">{error} Refresh the page to retry.</p>}
    {!data && !error && <p role="status" className="text-sm text-slate-400">Loading stored investigations…</p>}
    {data && <>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[
        ["Detected anomalies", data.anomalies], ["Active incidents", data.active_incidents],
        ["Completed investigations", data.investigations.completed], ["Failed investigations", data.investigations.failed],
      ].map(([label, value]) => <div key={label} className="rounded border border-line bg-surface-raised p-4"><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-2 text-2xl font-semibold text-white">{value}</dd></div>)}</dl>
      <p className="text-xs text-slate-400">Queued: {data.investigations.queued} · Running: {data.investigations.running}</p>
      <div className="grid gap-4 md:grid-cols-2"><div><h3 className="text-sm text-white">Severity distribution</h3><ul className="mt-2 flex flex-wrap gap-2 text-xs text-slate-300">{Object.entries(data.severity_distribution).map(([severity, count]) => <li key={severity} className="rounded border border-line px-3 py-2">{severity}: {count}</li>)}</ul></div>
        <div><h3 className="text-sm text-white">Evidence integrity</h3><p className="mt-2 text-xs text-slate-300">{data.integrity.resolved_citation_links}/{data.integrity.citation_links} hypothesis citation links resolve to stored IDs. {data.integrity.reports_needing_attention} reports need attention.</p><p className="mt-1 text-xs text-slate-500">Checked {data.integrity.audited_reports}/{data.integrity.completed_reports} completed reports (latest {data.integrity.scan_limit} maximum). ID resolution is not semantic verification.</p></div></div>
      <div><h3 className="text-sm text-white">Recent investigations</h3>{data.recent.length ? <ul className="mt-2 divide-y divide-line">{data.recent.map(job => <li key={job.investigation_id} className="py-2 text-xs"><Link className="text-cyan-accent underline" href={`/investigations/${job.investigation_id}`}>{job.investigation_id}</Link><span className="ml-3 text-slate-400">{job.status}</span><p className="mt-1 text-slate-400">{job.summary ?? "No completed report available."}</p></li>)}</ul> : <p className="mt-2 text-xs text-slate-400">No investigations have been saved in this store.</p>}</div>
    </>}
  </section>;
}
