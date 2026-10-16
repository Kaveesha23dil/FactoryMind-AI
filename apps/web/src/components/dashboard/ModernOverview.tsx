"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BrainCircuit, CircleAlert, Database, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import { apiFetch, getHealth } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { SubmissionOverview } from "@/types/submission";
import { AnimatedSeverityDonut, AnimatedJobBars } from "@/components/charts/AnimatedOverviewCharts";

const number = (value: number) => value.toLocaleString("en-US");
export default function ModernOverview() {
  const [data, setData] = useState<SubmissionOverview | null>(null);
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let stale = false;
    void Promise.allSettled([apiFetch<SubmissionOverview>("/api/submission/overview"), getHealth()]).then(([operations, health]) => {
      if (stale) return;
      if (operations.status === "fulfilled") { setData(operations.value); setError(null); }
      else setError("Unable to load operational data. Check backend connectivity and try again.");
      setConnected(health.status === "fulfilled" && health.value.status === "healthy");
      setChecking(false); setLoading(false);
    });
    return () => { stale = true; };
  }, [refresh]);
  function reload() { setLoading(true); setChecking(true); setConnected(false); setRefresh(value => value + 1); }
  const recent = [...(data?.recent ?? [])].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 5);
  const metrics = data ? [
    { label: "Detected Anomalies", value: data.anomalies, note: "Unusual benchmark observations", icon: Activity, tone: "lime", href: "/anomalies" },
    { label: "Active Incidents", value: data.active_incidents, note: "Open or under review", icon: TriangleAlert, tone: "mint", href: "/incidents" },
    { label: "Completed Investigations", value: data.investigations.completed, note: "Saved AI investigation reports", icon: BrainCircuit, tone: "lavender", href: "/investigations" },
    { label: "Investigation Failures", value: data.investigations.failed, note: "Execution errors requiring review", icon: CircleAlert, tone: "rose", href: "/investigations" },
  ] : [];
  let connection = "API unavailable";
  if (checking) connection = "Checking API…";
  else if (connected) connection = "API connected";
  return <div className="fm-overview fm-overview-refined">
    <header className="fm-topbar"><div className="fm-topbar-right"><span role="status" className={`fm-connection ${connected ? "is-connected" : ""}`}><i aria-hidden="true" />{connection}</span><span className="fm-avatar" aria-hidden="true">AF</span><div className="fm-team"><strong>AetherForge</strong><span>FactoryMind workspace</span></div></div></header>
    <div className="fm-content">
      <div className="fm-welcome"><div><h1>From Machine Anomalies to Explainable Decisions.</h1><p>Detect unusual operating conditions, investigate possible causes with Gemini, and explore evidence-backed recommendations.</p></div><div className="fm-demo-action">{data?.demo ? <Link href="/demo" className="fm-primary"><Sparkles size={16} />Explore AI Demo<ArrowUpRight size={16} /></Link> : <><button className="fm-primary" disabled aria-describedby="fm-demo-state"><Sparkles size={16} />Explore AI Demo</button><p id="fm-demo-state">{loading ? "Checking saved demo…" : "No verified saved demo available."}</p></>}</div></div>
      <div className="fm-section-title"><h2>Operations Overview <span>AI4I 2020 · Synthetic Dataset</span></h2><button className="fm-refresh" disabled={loading} onClick={reload}><RefreshCw size={14} className={loading ? "animate-spin" : ""} />{loading ? "Refreshing…" : "Refresh"}</button></div>
      <p className="fm-benchmark"><Database size={13} />Synthetic benchmark data · No live equipment control</p>
      {error && <div role="alert" className="fm-error">{error}{data && " Showing previously loaded values."} <button disabled={loading} onClick={reload}>Try again</button></div>}
      {!data && loading && <div className="fm-loading" role="status">Loading operational metrics and recent investigations…</div>}
      {data && <>
        <div className="fm-metrics" aria-label="Operational metrics">{metrics.map(item => { const Icon = item.icon; return <Link href={item.href} className={`fm-metric fm-${item.tone}`} key={item.label}><div className="fm-metric-top"><span><Icon size={17} aria-hidden="true" /></span><p>{item.label}</p></div><strong>{number(item.value)}</strong><small>{item.note}</small></Link>; })}</div>
        <div className="fm-charts">
          <section className="fm-panel"><div className="fm-panel-heading"><div><h2>Anomaly Breakdown</h2><p>Severity across detected anomalies</p></div><span className="fm-icon-circle"><Activity size={16} aria-hidden="true" /></span></div><AnimatedSeverityDonut data={data} /></section>
          <section className="fm-panel"><div className="fm-panel-heading"><div><h2>Investigation Overview</h2><p>Current status of persisted investigations</p></div><span className="fm-tag">All saved jobs</span></div><AnimatedJobBars investigations={data.investigations} /><p className="fm-chart-caption">Running and queued jobs are active. Failed jobs remain visible for review.</p></section>
        </div>
        <section className="fm-panel fm-recent" aria-busy={loading}><div className="fm-panel-heading"><div><h2>Recent AI Investigations</h2><p>Review the latest evidence-backed machine investigations.</p></div><Link href="/investigations" className="fm-text-link">View All Investigations<ArrowRight size={14} /></Link></div>
          <div className="fm-table-scroll" tabIndex={0} role="region" aria-label="Recent AI Investigations table"><table><thead><tr><th scope="col">Investigation ID</th><th scope="col">Incident ID</th><th scope="col">Primary Finding</th><th scope="col">Status</th><th scope="col">Created Date</th><th scope="col">Action</th></tr></thead><tbody>{recent.map(job => <tr key={job.investigation_id}><td><Link href={`/investigations/${job.investigation_id}`}>{job.investigation_id}</Link></td><td><Link href={`/incidents/${job.incident_id}`}>{job.incident_id}</Link></td><td className="fm-finding" title={job.summary ?? undefined}>{job.summary ?? "No completed report available"}</td><td><span className={`fm-status fm-status-${job.status}`}><i aria-hidden="true" />{job.status}</span></td><td><time dateTime={job.created_at}>{formatDateTime(job.created_at)}</time></td><td><Link className="fm-text-link" href={`/investigations/${job.investigation_id}`} aria-label={`View Report ${job.investigation_id}`}>View Report<ArrowUpRight size={13} /></Link></td></tr>)}</tbody></table>
          {!recent.length && <p className="fm-empty">No investigations yet. Create an incident and start an AI investigation to see results here.</p>}</div>
        </section>
      </>}
      <footer className="fm-footer"><span>FactoryMind AI <b>·</b>AetherForge</span><span>Evidence-backed recommendations require human review.</span></footer>
    </div>
  </div>;
}
