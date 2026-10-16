"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ClipboardList, Clock3, LockKeyhole, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { getInvestigation, getInvestigationEvidence, getInvestigations } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { loadMaintenance, type MaintenanceDraft, type MaintenanceSnapshot } from "@/lib/maintenance";
import InspectionDraft from "@/components/investigations/InspectionDraft";
import "./maintenance.css";

function TextList({ items, empty }: Readonly<{ items: string[]; empty: string }>) {
  if (!items.length) return <p className="mr-muted">{empty}</p>;
  return <ul className="mr-list">{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>;
}
function EvidenceDetails({ draft, ids, empty }: Readonly<{ draft: MaintenanceDraft; ids: string[]; empty: string }>) {
  if (!ids.length) return <p className="mr-muted">{empty}</p>;
  return <ul className="mr-evidence">{ids.map(id => {
    const record = draft.evidence.find(item => item.evidence_id === id);
    return <li key={id}><strong>{id}</strong><p>{record?.observation}</p><small>{record?.source} · {record?.provenance}</small></li>;
  })}</ul>;
}
function ReviewDetail({ draft }: Readonly<{ draft: MaintenanceDraft }>) {
  const review = draft.report.critic_review;
  return <section className="mr-detail mr-panel" aria-label="Inspection recommendation details">
    <div className="mr-detail-title"><div><span className="mr-eyebrow">INSPECTION DRAFT</span><h2>Recommendation details</h2></div><span className="mr-badge">Human review required</span></div>
    <Link className="mr-link" href={`/investigations/${draft.report.investigation_id}`}>Source {draft.report.investigation_id}<ArrowUpRight size={14} /></Link>
    <p className="mr-meta">Incident {draft.report.incident_id} · Saved {formatDateTime(draft.report.generated_at)}</p>
    {draft.report.counterfactual && <p className="mr-warning">What-if scenario {draft.report.counterfactual.scenario_id}: evidence was excluded. This hypothetical revision is not a new machine observation.</p>}
    <div className="mr-detail-block"><h3>Investigation summary</h3><p>{draft.report.summary}</p></div>
    <div className="mr-detail-block mr-proposed"><h3>Proposed inspection</h3><p>{draft.action.action}</p><p className="mr-muted">{draft.action.rationale}</p></div>
    <div className="mr-detail-block"><h3>Related hypotheses</h3>{draft.hypotheses.length ? draft.hypotheses.map(hypothesis => <article className="mr-hypothesis" key={hypothesis.hypothesis_id}><strong>{hypothesis.hypothesis_id} · {hypothesis.title}</strong><small>{hypothesis.assessment}</small><p>{hypothesis.description}</p><TextList items={hypothesis.verification_steps} empty="No additional verification steps recorded." /></article>) : <p className="mr-muted">No linked hypothesis is available. Resolve this before operational review.</p>}</div>
    <div className="mr-detail-block"><h3>Supporting evidence · {draft.supportingIds.length}</h3><EvidenceDetails draft={draft} ids={draft.supportingIds} empty="No supporting evidence resolves for the linked hypotheses." /></div>
    <div className="mr-detail-block"><h3>Contradicting evidence · {draft.contradictingIds.length}</h3><EvidenceDetails draft={draft} ids={draft.contradictingIds} empty="No contradicting evidence recorded for these hypotheses; this does not establish confirmation." /></div>
    {!!draft.unresolvedIds.length && <div className="mr-warning" role="alert">Unresolved evidence references: {draft.unresolvedIds.join(", ")}. These are excluded from the evidence counts.</div>}
    <div className="mr-detail-block"><h3>Missing information</h3><TextList items={draft.missingInformation} empty="No additional missing information recorded. Independent technician verification is still required." /></div>
    <div className="mr-detail-block"><h3>Critic verification notes</h3><p>{review.verification_outcome}</p><TextList items={draft.concerns} empty="No additional critic concerns recorded. This is not technician approval." />{!!review.alternative_explanations.length && <><h4>Alternative explanations</h4><TextList items={review.alternative_explanations} empty="" /></>}</div>
    <div className="mr-unavailable"><LockKeyhole size={15} /><p>Technician approval workflow is not available in this prototype.</p></div>
    <InspectionDraft report={draft.report} />
    <p className="mr-meta">Downloads the complete source investigation draft, including all its recommendations. Opening this panel does not record a review state.</p>
  </section>;
}

export default function MaintenanceReview() {
  const [snapshot, setSnapshot] = useState<MaintenanceSnapshot | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const detailRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => { if (selectedId) detailRef.current?.focus(); }, [selectedId]);
  useEffect(() => {
    let stale = false;
    void loadMaintenance({ list: offset => getInvestigations({ status: "completed", limit: 100, offset }), job: getInvestigation, evidence: getInvestigationEvidence }, () => stale).then(next => {
      if (stale) return;
      setSnapshot(next); setError(""); setLoading(false);
      setSelectedId(current => next.drafts.some(draft => draft.id === current) ? current : null);
    }).catch(() => { if (!stale) { setError("Unable to load saved recommendations or verify their evidence. Check backend access and retry."); setLoading(false); } });
    return () => { stale = true; };
  }, [refresh]);
  function reload() { setLoading(true); setRefresh(value => value + 1); }
  const selected = snapshot?.drafts.find(draft => draft.id === selectedId);
  return <main className="mr-page">
    <header className="mr-header"><div><span className="mr-eyebrow">WORKSPACE / MAINTENANCE</span><h1>Maintenance Review</h1><p>Review evidence-backed inspection recommendations generated from AI investigations.</p></div><button className="mr-button" disabled={loading} onClick={reload}><RefreshCw size={14} />{loading ? "Loading…" : "Refresh"}</button></header>
    <div className="mr-metrics" role="group" aria-label="Maintenance summary"><div className="mr-metric mr-available"><ClipboardList size={19} /><h2>Available Drafts</h2><strong>{snapshot ? snapshot.drafts.length : "—"}</strong><p>Saved inspection recommendations</p></div><div className="mr-metric"><Clock3 size={19} /><h2>Under Review</h2><strong className="mr-untracked">Unavailable</strong><p>Technician review state is not tracked</p></div><div className="mr-metric"><ShieldCheck size={19} /><h2>Approved</h2><strong className="mr-untracked">Unavailable</strong><p>Persisted approval is not implemented</p></div></div>
    {error && <div className="mr-warning" role="alert">{error}{snapshot && " Previously loaded drafts remain visible."}<button disabled={loading} onClick={reload}>Retry</button></div>}
    {loading && <div className="mr-loading" role="status">Reading saved investigations and evidence…</div>}
    {snapshot && <>
      <div className="mr-section-heading"><div><h2>Inspection recommendations</h2><p>{snapshot.drafts.length} draft recommendations from {snapshot.eligibleReports} saved Google-provider reports. Drafts are recommendations, not maintenance tickets.</p></div><Link className="mr-link" href="/investigations">View AI Investigations<ArrowUpRight size={14} /></Link></div>
      {!snapshot.drafts.length && !loading && <section className="mr-empty mr-panel"><ClipboardList size={26} /><h2>No maintenance drafts available</h2><p>Complete an AI investigation to generate an evidence-backed inspection recommendation.</p><Link className="mr-button mr-primary" href="/investigations">View AI Investigations</Link></section>}
      <div className={`mr-workspace ${selected ? "mr-has-detail" : ""}`}>
        <div className="mr-recommendations">{snapshot.drafts.map(draft => <article className={`mr-recommendation mr-panel ${selectedId === draft.id ? "mr-selected" : ""}`} key={draft.id}>
          <div className="mr-card-top"><Link className="mr-link" href={`/investigations/${draft.report.investigation_id}`}>{draft.report.investigation_id}</Link><span className="mr-badge">{draft.report.counterfactual ? "What-if draft" : "Draft only"}</span></div>
          <Link className="mr-incident" href={`/incidents/${draft.report.incident_id}`}>{draft.report.incident_id}</Link>
          <h3>{draft.action.action}</h3><p className="mr-card-hypothesis"><span>Primary hypothesis</span>{draft.hypotheses[0]?.title ?? "No linked hypothesis recorded"}</p>
          <div className="mr-card-facts"><span>{draft.supportingIds.length} supporting evidence IDs</span><span>{draft.concerns.length} report critic concerns</span>{!!draft.unresolvedIds.length && <span className="mr-concern">{draft.unresolvedIds.length} unresolved references</span>}</div>
          <p className="mr-card-concerns">{draft.concerns[0] ?? "No critic concerns recorded; qualified review is still required."}</p>
          <div className="mr-card-bottom"><small>Human review required · draft only</small><button className="mr-button" aria-expanded={selectedId === draft.id} aria-label={`View Details ${draft.id}`} onClick={event => { triggerRef.current = event.currentTarget; setSelectedId(draft.id); }}>View Details<ArrowUpRight size={13} /></button></div>
        </article>)}</div>
        {selected && <div ref={detailRef} tabIndex={-1}><button className="mr-close" onClick={() => { setSelectedId(null); triggerRef.current?.focus(); }}>Close details</button><ReviewDetail draft={selected} /></div>}
      </div>
    </>}
    <aside className="mr-safety"><TriangleAlert size={18} /><div><h2>Technician review required</h2><p>AI-generated recommendations support technician decision-making. They do not confirm equipment failures or execute physical maintenance actions.</p><p>A qualified technician must review all recommendations before any operational action. AI4I observations and packaged references are synthetic benchmark material.</p><p>Technician approval workflow is not available in this prototype.</p></div></aside>
  </main>;
}
