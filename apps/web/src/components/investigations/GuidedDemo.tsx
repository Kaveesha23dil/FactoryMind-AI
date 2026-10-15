"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, getAnomaly, getInvestigation } from "@/lib/api";
import type { SubmissionOverview } from "@/types/submission";
import type { InvestigationJob } from "@/types/investigation";
import type { AnomalyDetail } from "@/types/anomaly";
import EvidenceGraphView from "@/components/investigations/EvidenceGraphView";

export default function GuidedDemo() {
  const [data, setData] = useState<{ overview: SubmissionOverview; job: InvestigationJob | null; anomaly: AnomalyDetail | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let stale = false;
    void (async () => {
      const overview = await apiFetch<SubmissionOverview>("/api/submission/overview");
      const [job, anomaly] = overview.demo ? await Promise.all([getInvestigation(overview.demo.investigation_id), getAnomaly(overview.demo.record_id)]) : [null, null];
      if (!stale) setData({ overview, job, anomaly });
    })().catch(reason => { if (!stale) setError(reason instanceof Error ? reason.message : "Saved demo unavailable"); });
    return () => { stale = true; };
  }, []);
  const demo = data?.overview.demo;
  const report = data?.job?.report;
  return <main className="space-y-6 p-6 lg:p-8">
    <h1 className="text-2xl font-semibold text-white">Guided Demo · Saved results</h1>
    <p className="max-w-3xl text-sm text-slate-400">This walkthrough reads persisted results. It starts no Gemini requests and operates no equipment. AI4I records and maintenance guidance are synthetic benchmark/reference material.</p>
    {error && <p role="alert" className="text-warning">{error} Refresh to retry.</p>}
    {!data && !error && <p role="status" className="text-slate-400">Checking saved report and source references…</p>}
    {data && !demo && <section className="rounded border border-line p-5 text-slate-300"><h2>No eligible saved Google-provider report in this store</h2><p className="mt-2 text-sm">A completed report with all four agent records, resolvable evidence IDs and matching source passages is required. Import a reviewed saved run or complete a new investigation when quota permits. No result has been substituted.</p><Link className="mt-3 inline-block text-cyan-accent underline" href="/incidents">Open incidents</Link></section>}
    {demo && report && <>
      <section className="rounded border border-warning/40 bg-warning/5 p-5 text-sm text-slate-300"><h2 className="font-semibold text-white">Historical result · {demo.investigation_id}</h2><p className="mt-2">{demo.label} Saved {demo.generated_at} · {demo.model}.</p><p className="mt-2">{demo.audit.resolved_citation_links}/{demo.audit.citation_links} citation links resolve; source passages match the current packaged corpus. {demo.audit.relationship_reviews_available ? "Relationship-level critic audit is present." : "This historical report predates relationship-level validation."} {demo.audit.critic_attention_required && "The critic flagged unresolved issues; this is not an accepted diagnosis."}</p></section>
      <section className="rounded border border-line bg-surface p-5"><h2 className="font-semibold text-white">1. Abnormal benchmark observation</h2><p className="mt-2 text-sm text-slate-300">Record {demo.record_id} · anomaly score {data?.anomaly?.anomaly_score} · severity {data?.anomaly?.severity}. Severity is application-defined, not a calibrated failure probability.</p><ul className="mt-3 space-y-2 text-sm text-slate-400">{data?.anomaly?.anomalous_features.map(feature => <li key={feature.feature}>{feature.explanation}</li>)}</ul></section>
      <section className="rounded border border-line bg-surface p-5"><h2 className="font-semibold text-white">2. Saved multi-agent interpretation</h2><p className="mt-2 text-sm text-slate-300">{report.summary}</p><p className="mt-2 text-xs text-slate-500">Candidate explanations require technician verification. No new reasoning has run.</p></section>
      <section><h2 className="mb-3 font-semibold text-white">3. Inspect stored evidence relationships</h2><EvidenceGraphView investigationId={demo.investigation_id} /></section>
      <section className="rounded border border-line bg-surface p-5"><h2 className="font-semibold text-white">4. Critic assessment</h2><p className="mt-2 text-sm text-slate-300">Recorded outcome: {report.critic_review.verification_outcome}. Review the issues even when the historical revision flag is false.</p><ul className="mt-3 list-inside list-disc space-y-2 text-sm text-warning">{[...report.critic_review.issues_found, ...report.critic_review.citation_issues].map((issue, index) => <li key={`${index}-${issue}`}>{issue}</li>)}</ul></section>
      <section className="rounded border border-line bg-surface p-5"><h2 className="font-semibold text-white">5. Technician review draft</h2><p className="mt-2 text-xs text-slate-400">Recommendations from the saved report. No ticket, approval or maintenance action has been executed. Follow site procedures and qualified-person review.</p><ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-300">{report.recommended_actions.map((action, index) => <li key={`${index}-${action.action}`}>{action.action}</li>)}</ul></section>
      <section className="rounded border border-line bg-surface p-5 text-sm text-slate-300"><h2 className="font-semibold text-white">6. Continue the investigation</h2><p className="mt-2">Saved counterfactuals, when available, can be inspected in What-if. Creating a new scenario genuinely reruns reasoning and consumes quota; no saved comparison is invented here.</p><Link className="mt-3 inline-block text-cyan-accent underline" href={`/investigations/${demo.investigation_id}`}>Open report, sources and What-if →</Link><p className="mt-3 text-xs text-slate-500">Use the incident workflow for a new live investigation only when quota is available.</p></section>
    </>}
  </main>;
}
