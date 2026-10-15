"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowRight, ArrowUpRight, BookOpen, CheckCheck, Database, FlaskConical, Layers3, RefreshCw, Search, ShieldCheck, Sparkles, TriangleAlert } from "lucide-react";
import { apiFetch, getDatasetSummary, getHealth } from "@/lib/api";
import type { SubmissionOverview } from "@/types/submission";
import type { DatasetSummary } from "@/types/monitoring";

import { AnimatedSeverityDonut, AnimatedJobBars } from "@/components/charts/AnimatedOverviewCharts";
const number = (value: number) => value.toLocaleString("en-US");

export default function ModernOverview() {
  const [data, setData] = useState<SubmissionOverview | null>(null);
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  useEffect(() => {
    let stale = false;
    void Promise.allSettled([apiFetch<SubmissionOverview>("/api/submission/overview"), getDatasetSummary(), getHealth()]).then(([operations, dataset, health]) => {
      if (stale) return;
      if (operations.status === "fulfilled") { setData(operations.value); setError(null); }
      else setError(operations.reason instanceof Error ? operations.reason.message : "Unable to load investigation records.");
      if (dataset.status === "fulfilled") setSummary(dataset.value);
      setConnected(health.status === "fulfilled" && health.value.status === "healthy"); setLoading(false);
    });
    return () => { stale = true; };
  }, [refresh]);
  const recent = data?.recent.filter(item => (status === "all" || item.status === status) && `${item.investigation_id} ${item.summary ?? ""}`.toLowerCase().includes(query.toLowerCase())) ?? [];
  const states = ["completed", "failed", "running", "queued"];
  const metrics = data ? [
    { label: "Detected anomalies", value: data.anomalies, note: "Unusual benchmark observations", icon: Activity, tone: "lime", href: "/anomalies" },
    { label: "Active incidents", value: data.active_incidents, note: "Open or under review", icon: Layers3, tone: "mint", href: "/incidents" },
    { label: "Failed investigations", value: data.investigations.failed, note: "Review errors before retrying", icon: TriangleAlert, tone: "rose", href: "/investigations" },
    { label: "Completed reports", value: data.investigations.completed, note: "Saved investigation results", icon: CheckCheck, tone: "lavender", href: "/investigations" },
  ] : [];
  return <div className="fm-overview">
    <header className="fm-topbar"><div className="fm-breadcrumb">Workspace <span>/</span> <b>Overview</b></div><div className="fm-topbar-right"><span className={`fm-connection ${connected ? "is-connected" : ""}`}><i />{connected ? "API connected" : "API checking / unavailable"}</span><span className="fm-avatar">AF</span><div className="fm-team"><strong>AetherForge</strong><span>FactoryMind workspace</span></div></div></header>
    <div className="fm-content"><div className="fm-welcome"><div><div className="fm-eyebrow"><span /> YOUR OPERATIONS, EXPLAINED</div><h1>A clearer view of your factory<span>.</span></h1><p>From unusual observations to evidence-backed investigation.</p></div><Link href="/demo" className="fm-primary"><Sparkles size={16} /> Guided saved demo <ArrowUpRight size={16} /></Link></div>
      <div className="fm-section-title"><h2>Workspace at a glance <span>AI4I 2020</span></h2><button className="fm-refresh" disabled={loading} onClick={() => { setLoading(true); setRefresh(value => value + 1); }}><RefreshCw size={14} className={loading ? "animate-spin" : ""} />{loading ? "Refreshing" : "Refresh data"}</button></div>
      <p className="fm-benchmark"><Database size={13} /> Synthetic benchmark data · not live machine telemetry · no equipment control</p>
      {error && <div role="alert" className="fm-error">{error} <button onClick={() => { setLoading(true); setRefresh(value => value + 1); }}>Try again</button></div>}
      {!data && loading && <div className="fm-loading" role="status">Loading your workspace…</div>}
      {data && <><div className="fm-metrics">{metrics.map(item => { const Icon = item.icon; return <Link href={item.href} className={`fm-metric fm-${item.tone}`} key={item.label}><div className="fm-metric-top"><span><Icon size={17} /></span><ArrowUpRight size={16} /></div><p>{item.label}</p><strong>{number(item.value)}</strong><small>{item.note}</small><Icon className="fm-metric-art" size={72} strokeWidth={1.2} aria-hidden="true" /></Link>; })}</div>
        <div className="fm-charts"><section className="fm-panel"><div className="fm-panel-heading"><div><h2>Anomaly breakdown</h2><p>Severity across detected anomalies</p></div><span className="fm-icon-circle"><Activity size={16} /></span></div><AnimatedSeverityDonut data={data} /></section>
          <section className="fm-panel"><div className="fm-panel-heading"><div><h2>Investigation overview</h2><p>Current status of persisted jobs</p></div><span className="fm-tag">All saved jobs</span></div><AnimatedJobBars investigations={data.investigations} /><p className="fm-chart-caption"><span /> Failed jobs stay visible. Reports require human review.</p></section></div>
        <div className="fm-bottom-grid"><section className="fm-panel fm-recent"><div className="fm-panel-heading"><div><h2>Recent investigations</h2><p>Latest {data.recent.length} saved records</p></div><Link href="/investigations" className="fm-text-link">View all <ArrowRight size={14} /></Link></div><div className="fm-table-controls"><label className="fm-search"><Search size={15} /><input aria-label="Search recent investigations" placeholder="Search ID or finding…" value={query} onChange={event => setQuery(event.target.value)} /></label><select aria-label="Filter recent investigations by status" value={status} onChange={event => setStatus(event.target.value)}><option value="all">All statuses</option>{states.map(key => <option key={key} value={key}>{key}</option>)}</select></div><div className="fm-table-scroll"><table><thead><tr><th>Investigation</th><th>Finding / progress</th><th>Status</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{recent.map(job => <tr key={job.investigation_id}><td><span className="fm-row-icon"><FlaskConical size={15} /></span><Link href={`/investigations/${job.investigation_id}`}>{job.investigation_id}</Link></td><td className="fm-finding">{job.summary ?? "No completed report available"}</td><td><span className={`fm-status fm-status-${job.status}`}><i />{job.status}</span></td><td><Link href={`/investigations/${job.investigation_id}`} aria-label={`Open ${job.investigation_id}`}><ArrowUpRight size={16} /></Link></td></tr>)}</tbody></table>{!recent.length && <p className="fm-empty">{data.recent.length ? "No recent records match your filters." : "No saved investigations yet. Start from an incident."}</p>}</div></section>
          <section className="fm-panel fm-integrity"><span className="fm-integrity-icon"><ShieldCheck size={23} /></span><h2>Evidence you can inspect</h2><p>Trace conclusions back to the observations behind them.</p><div className="fm-integrity-number">{data.integrity.resolved_citation_links}<span> / {data.integrity.citation_links}</span></div><p className="fm-integrity-caption">hypothesis citation IDs resolve</p><div className="fm-attention"><TriangleAlert size={15} /><span>{data.integrity.reports_needing_attention} reports need attention</span></div><p className="fm-fine-print">Checked {data.integrity.audited_reports} of {data.integrity.completed_reports} completed reports, latest {data.integrity.scan_limit} maximum. ID resolution does not prove semantic accuracy.</p><Link href="/demo" className="fm-text-link">Inspect saved walkthrough <ArrowRight size={14} /></Link></section></div></>}
      {summary && <section className="fm-dataset"><div><BookOpen size={18} /><span><strong>Know your data</strong><small>AI4I 2020 · synthetic benchmark · no chronological machine history</small></span></div><dl><div><dt>Dataset records</dt><dd>{number(summary.record_count)}</dd></div><div><dt>No failure labeled</dt><dd>{number(summary.normal_count)}</dd></div><div><dt>Failure labeled</dt><dd>{number(summary.failure_count)}</dd></div><div><dt>Failure rate</dt><dd>{(summary.failure_rate * 100).toFixed(2)}%</dd></div></dl><span className="fm-data-note">Labels are for evaluation, never investigation inputs.</span></section>}
      <footer className="fm-footer"><span>FactoryMind AI <b>·</b> AetherForge</span><span>Built for investigation. Designed for human judgment.</span></footer>
    </div></div>;
}

