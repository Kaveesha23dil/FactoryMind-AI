import type { EvidenceListResponse, EvidenceRecord, Hypothesis, InvestigationJob, InvestigationListPage, InvestigationReport, RecommendedAction } from "../types/investigation";

export type MaintenanceDraft = {
  id: string;
  action: RecommendedAction;
  report: InvestigationReport;
  hypotheses: Hypothesis[];
  evidence: EvidenceRecord[];
  supportingIds: string[];
  contradictingIds: string[];
  unresolvedIds: string[];
  missingInformation: string[];
  concerns: string[];
};
export type MaintenanceSnapshot = { drafts: MaintenanceDraft[]; completedReports: number; eligibleReports: number };
type ReadAPI = Readonly<{
  list: (offset: number) => Promise<InvestigationListPage>;
  job: (id: string) => Promise<InvestigationJob>;
  evidence: (id: string) => Promise<EvidenceListResponse>;
}>;
const unique = (items: string[]) => [...new Set(items)];

export function buildMaintenanceDrafts(job: InvestigationJob, records: EvidenceRecord[]): MaintenanceDraft[] {
  const report = job.report;
  if (job.status !== "completed" || job.provider !== "google") return [];
  if (!report || report.status !== "completed" || report.provider !== "google") throw new Error("Completed Google-provider job has no matching completed report.");
  if (report.investigation_id !== job.investigation_id || report.incident_id !== job.incident_id) throw new Error("Investigation report ownership does not match the saved job.");
  if (records.some(record => record.investigation_id !== job.investigation_id || record.incident_id !== job.incident_id)) throw new Error("Stored evidence belongs to a different investigation.");
  const critic = report.critic_review;
  const concerns = unique([...critic.issues_found, ...critic.citation_issues, ...critic.unsupported_claims, ...critic.contradictions, ...critic.deterministic_findings, ...critic.excluded_evidence_reused.map(id => `Excluded evidence reused: ${id}`), ...(critic.citation_reviews ?? []).filter(review => !review.valid).map(review => `${review.evidence_id}: ${review.reason}`)]);
  if (critic.revision_required && !concerns.length) concerns.push("The critic requested a revision.");
  const byId = new Map(records.map(record => [record.evidence_id, record]));
  const catalog = new Set(report.evidence_catalog);
  return report.recommended_actions.filter(action => action.action.trim()).map((action, index) => {
    const hypotheses = report.hypotheses.filter(hypothesis => action.supporting_hypothesis_ids.includes(hypothesis.hypothesis_id));
    const supporting = unique(hypotheses.flatMap(hypothesis => hypothesis.supporting_evidence_ids));
    const contradicting = unique(hypotheses.flatMap(hypothesis => hypothesis.contradicting_evidence_ids));
    const ids = unique([...supporting, ...contradicting]);
    const resolves = (id: string) => {
      const record = byId.get(id);
      return !!record?.source?.trim() && !!record.provenance?.trim() && catalog.has(id);
    };
    const missingHypotheses = action.supporting_hypothesis_ids.filter(id => !hypotheses.some(hypothesis => hypothesis.hypothesis_id === id));
    const missingInformation = unique([...hypotheses.flatMap(hypothesis => hypothesis.missing_evidence), ...critic.missing_evidence, ...missingHypotheses.map(id => `Unknown supporting hypothesis: ${id}`)]);
    if (!hypotheses.length) missingInformation.push("No supporting hypothesis is linked to this action.");
    return { id: `${job.investigation_id}:${index}`, action, report, hypotheses,
      evidence: records.filter(record => ids.includes(record.evidence_id) && catalog.has(record.evidence_id)),
      supportingIds: supporting.filter(resolves), contradictingIds: contradicting.filter(resolves),
      unresolvedIds: ids.filter(id => !resolves(id)), missingInformation, concerns };
  });
}

/** Read every completed-job page; a failed page/report never becomes a fabricated empty result. */
export async function loadMaintenance(api: ReadAPI, cancelled: () => boolean = () => false): Promise<MaintenanceSnapshot> {
  const jobs = new Map<string, { investigation_id: string; provider: string }>();
  let offset = 0;
  let total = 0;
  do {
    if (cancelled()) throw new Error("Maintenance loading cancelled.");
    const page = await api.list(offset);
    total = page.total;
    if (!page.items.length && offset < total) throw new Error("Investigation pagination was incomplete. Refresh to try again.");
    for (const job of page.items) jobs.set(job.investigation_id, job);
    offset += page.items.length;
  } while (offset < total);
  const eligible = [...jobs.values()].filter(job => job.provider === "google");
  const drafts: MaintenanceDraft[] = [];
  for (let start = 0; start < eligible.length; start += 4) {
    if (cancelled()) throw new Error("Maintenance loading cancelled.");
    const batch = await Promise.all(eligible.slice(start, start + 4).map(async item => {
      const [job, evidence] = await Promise.all([api.job(item.investigation_id), api.evidence(item.investigation_id)]);
      if (evidence.investigation_id !== job.investigation_id || evidence.incident_id !== job.incident_id) throw new Error("Evidence response ownership does not match the investigation.");
      return buildMaintenanceDrafts(job, evidence.items);
    }));
    drafts.push(...batch.flat());
  }
  return { drafts, completedReports: jobs.size, eligibleReports: eligible.length };
}
