"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  BrainCircuit,
  CheckCircle2,
  FlaskConical,
  GitCompareArrows,
  Image as ImageIcon,
  ListChecks,
  Loader2,
  Network,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import {
  getInvestigation,
  getInvestigationEvidence,
} from "@/lib/api";
import type {
  AgentActivity,
  EvidenceListResponse,
  Hypothesis,
  InvestigationJob,
} from "@/types/investigation";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui/Feedback";
import EvidenceGraphView from "@/components/investigations/EvidenceGraphView";
import CounterfactualPanel from "@/components/investigations/CounterfactualPanel";
import VisualInspectionPanel from "@/components/investigations/VisualInspectionPanel";
import {
  AGENT_ORDER,
  AGENT_STATUS_LABELS,
  AGENT_STATUS_TONE,
  EVIDENCE_TYPE_LABELS,
  HYPOTHESIS_ASSESSMENT_LABELS,
  HYPOTHESIS_ASSESSMENT_TONE,
  INVESTIGATION_STATUS_LABELS,
  INVESTIGATION_STATUS_TONE,
  isTerminalInvestigation,
  labelForStage,
} from "@/lib/investigations";
import { cn, formatDateTime } from "@/lib/format";

const POLL_INTERVAL_MS = 2500;

type WorkspaceTab = "report" | "graph" | "counterfactual" | "visual";

const WORKSPACE_TABS: Array<{
  id: WorkspaceTab;
  label: string;
  icon: typeof BrainCircuit;
}> = [
  { id: "report", label: "Report", icon: FlaskConical },
  { id: "graph", label: "Evidence graph", icon: Network },
  { id: "counterfactual", label: "What-if", icon: GitCompareArrows },
  { id: "visual", label: "Visual inspection", icon: ImageIcon },
];

const ROW_TONES: Record<"neutral" | "success" | "danger" | "accent" | "warning", string> = {
  neutral: "border-neutral-700/40 bg-neutral-500/5 text-slate-300",
  success: "border-success/40 bg-success/5 text-success",
  danger: "border-danger/40 bg-danger/5 text-danger",
  accent: "border-cyan-accent/40 bg-cyan-accent/5 text-cyan-accent",
  warning: "border-warning/40 bg-warning/5 text-warning",
};

interface InvestigationWorkspaceProps {
  investigationId: string;
}

export default function InvestigationWorkspace({
  investigationId,
}: InvestigationWorkspaceProps) {
  const [job, setJob] = useState<InvestigationJob | null>(null);
  const [evidence, setEvidence] = useState<EvidenceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<WorkspaceTab>("report");

  useEffect(() => {
    let stale = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    (async () => {
      try {
        const [nextJob, nextEvidence] = await Promise.all([
          getInvestigation(investigationId),
          getInvestigationEvidence(investigationId),
        ]);
        if (stale) return;
        setJob(nextJob);
        setEvidence(nextEvidence);
        setError(null);
        setLoading(false);
        setRefreshing(false);
        if (!isTerminalInvestigation(nextJob.status)) {
          timer = setTimeout(() => setTick((value) => value + 1), POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (stale) return;
        setError(
          err instanceof Error
            ? err.message
            : "Unexpected error while loading the investigation."
        );
        setLoading(false);
        setRefreshing(false);
      }
    })();

    return () => {
      stale = true;
      if (timer) clearTimeout(timer);
    };
  }, [investigationId, tick]);

  const report = job?.report ?? null;
  const active = job ? !isTerminalInvestigation(job.status) : false;

  const evidenceById = useMemo(() => {
    const map = new Map<string, { observation: string; source: string }>();
    for (const item of evidence?.items ?? []) {
      map.set(item.evidence_id, {
        observation: item.observation,
        source: item.source,
      });
    }
    return map;
  }, [evidence]);

  const refresh = () => {
    setRefreshing(true);
    setTick((value) => value + 1);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          <Link
            href="/investigations"
            className="underline-offset-2 hover:text-slate-200 hover:underline"
          >
            All investigations
          </Link>
        </div>

        {loading ? (
          <CardSkeleton />
        ) : error ? (
          <ErrorState
            title="Could not load investigation"
            message={error}
            onRetry={refresh}
          />
        ) : !job ? (
          <EmptyState
            title="Investigation not found"
            description="No investigation matches the requested identifier."
          />
        ) : (
          <>
            <header className="rounded-lg border border-line bg-surface px-5 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <BrainCircuit className="h-4 w-4 text-cyan-accent" aria-hidden="true" />
                    <h1 className="text-sm font-semibold text-white">
                      {job.investigation_id}
                    </h1>
                    <StatusBadge
                      label={INVESTIGATION_STATUS_LABELS[job.status]}
                      tone={INVESTIGATION_STATUS_TONE[job.status]}
                      dot
                    />
                    <StatusBadge label={labelForStage(job.stage)} tone="neutral" />
                    {active && (
                      <span className="inline-flex items-center gap-1.5 text-xs text-cyan-accent">
                        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                        Auto-refreshing
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400">
                    Incident{" "}
                    <Link
                      href={`/incidents/${job.incident_id}`}
                      className="font-medium text-cyan-accent underline-offset-2 hover:underline"
                    >
                      {job.incident_id}
                    </Link>{" "}
                    · Provider <span className="text-slate-300">{job.provider}</span> · Model{" "}
                    <span className="font-mono text-[11px] text-slate-300">{job.model}</span>
                  </p>
                  {job.summary && (
                    <p className="max-w-3xl text-xs leading-relaxed text-slate-300">
                      {job.summary}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={refresh}
                  disabled={refreshing || active}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshCw
                    className={cn("h-3.5 w-3.5", refreshing && "animate-spin")}
                    aria-hidden="true"
                  />
                  Refresh
                </button>
              </div>

              {job.status === "failed" && (
                <div className="mt-4 flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
                  <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="font-medium">
                      The investigation failed after attempt {job.attempt_count}.
                    </p>
                    {job.error && <p className="mt-0.5 break-words">{job.error}</p>}
                  </div>
                </div>
              )}
            </header>

            <AgentTimeline activities={job.agent_activity} />
            <StageHistory job={job} />

            <WorkspaceTabs tab={tab} onChange={setTab} />

            {tab === "report" && (
              <>
                {report ? (
                  <ReportView report={report} evidenceById={evidenceById} />
                ) : (
                  <section className="rounded-lg border border-dashed border-line px-5 py-8 text-center">
                    <p className="text-xs text-slate-400">
                      {active
                        ? "The multi-agent pipeline is still running. Findings will appear here when complete."
                        : job.status === "failed"
                          ? "No report was produced."
                          : "No report available."}
                    </p>
                  </section>
                )}

                <EvidenceTable evidence={evidence} active={active} />
              </>
            )}

            {tab === "graph" && (
              <EvidenceGraphView investigationId={investigationId} />
            )}

            {tab === "counterfactual" && (
              <CounterfactualPanel
                investigationId={investigationId}
                evidence={evidence}
              />
            )}

            {tab === "visual" && (
              <VisualInspectionPanel
                incidentId={job.incident_id}
                investigationId={investigationId}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function WorkspaceTabs({
  tab,
  onChange,
}: {
  tab: WorkspaceTab;
  onChange: (tab: WorkspaceTab) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Investigation views"
      className="flex flex-wrap gap-1 rounded-lg border border-line bg-surface p-1"
    >
      {WORKSPACE_TABS.map((item) => {
        const Icon = item.icon;
        const selected = item.id === tab;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(item.id)}
            className={cn(
              "inline-flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
              selected
                ? "bg-surface-raised text-white"
                : "text-slate-400 hover:bg-surface-raised/60 hover:text-slate-200"
            )}
          >
            <Icon
              className={cn("h-3.5 w-3.5", selected ? "text-cyan-accent" : "text-slate-500")}
              aria-hidden="true"
            />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

function AgentTimeline({ activities }: { activities: AgentActivity[] }) {
  const ordered = [...activities].sort((a, b) => {
    const ai = AGENT_ORDER.indexOf(a.agent as (typeof AGENT_ORDER)[number]);
    const bi = AGENT_ORDER.indexOf(b.agent as (typeof AGENT_ORDER)[number]);
    return (ai === -1 ? AGENT_ORDER.length : ai) - (bi === -1 ? AGENT_ORDER.length : bi);
  });

  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold text-white">Agent activity</h2>
        <p className="mt-1 text-xs text-slate-400">
          Each agent contributes evidence and reasoning; the critic agent verifies the final report.
        </p>
      </div>
      {ordered.length === 0 ? (
        <p className="px-5 py-6 text-xs text-slate-400">No agent activity recorded yet.</p>
      ) : (
        <ol className="divide-y divide-line/60">
          {ordered.map((activity) => (
            <li key={activity.agent} className="flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex items-start gap-3">
                <FlaskConical
                  className={cn(
                    "mt-0.5 h-4 w-4 shrink-0",
                    activity.status === "completed" && "text-success",
                    activity.status === "failed" && "text-danger",
                    activity.status === "running" && "text-cyan-accent",
                    (activity.status === "pending" ||
                      activity.status === "skipped") && "text-slate-600"
                  )}
                  aria-hidden="true"
                />
                <div>
                  <p className="text-xs font-medium text-slate-200">{activity.label}</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">{activity.agent}</p>
                  {activity.summary && (
                    <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-400">
                      {activity.summary}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3 sm:flex-col sm:items-end sm:gap-1">
                <StatusBadge
                  label={AGENT_STATUS_LABELS[activity.status]}
                  tone={AGENT_STATUS_TONE[activity.status]}
                  dot
                />
                <span className="text-[11px] text-slate-500 tabular-nums">
                  {activity.evidence_count !== null && activity.evidence_count !== undefined
                    ? `${activity.evidence_count} evidence`
                    : activity.completed_at
                      ? formatDateTime(activity.completed_at)
                      : ""}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function StageHistory({ job }: { job: InvestigationJob }) {
  if (job.stage_history.length === 0) return null;
  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold text-white">Pipeline stages</h2>
      </div>
      <ol className="divide-y divide-line/60">
        {job.stage_history.map((entry, index) => (
          <li key={`${entry.stage}-${index}`} className="flex items-start gap-3 px-5 py-3">
            <span
              className={cn(
                "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                index === job.stage_history.length - 1 ? "bg-cyan-accent" : "bg-slate-600"
              )}
              aria-hidden="true"
            />
            <div className="flex flex-1 flex-wrap items-baseline justify-between gap-2">
              <p className="text-xs font-medium text-slate-200">{labelForStage(entry.stage)}</p>
              {entry.message && <p className="max-w-xl text-[11px] text-slate-400">{entry.message}</p>}
              <p className="text-[11px] text-slate-500 tabular-nums">{formatDateTime(entry.timestamp)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

interface ReportViewProps {
  report: NonNullable<InvestigationJob["report"]>;
  evidenceById: Map<string, { observation: string; source: string }>;
}

function ReportView({ report, evidenceById }: ReportViewProps) {
  return (
    <section className="space-y-6" aria-label="Investigation report">
      {report.counterfactual && (
        <div className="flex items-start gap-2 rounded-lg border border-cyan-accent/30 bg-cyan-accent/5 px-4 py-3 text-xs text-slate-300">
          <GitCompareArrows className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan-accent" aria-hidden="true" />
          <div>
            <p className="font-medium text-white">
              Counterfactual revision{" "}
              <span className="font-mono text-cyan-accent">
                {report.counterfactual.scenario_id}
              </span>
            </p>
            <p className="mt-0.5 text-slate-400">
              This report was produced with {report.counterfactual.excluded_evidence_ids.length}{" "}
              evidence record
              {report.counterfactual.excluded_evidence_ids.length === 1 ? "" : "s"} withheld from the
              original investigation{" "}
              <span className="font-mono">
                {report.counterfactual.original_investigation_id}
              </span>
              .
            </p>
          </div>
        </div>
      )}
      <div className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-white">Findings</h2>
          <p className="text-[11px] text-slate-500 tabular-nums">
            Drafted {formatDateTime(report.generated_at)} ·{" "}
            {report.revision_count === 0
              ? "no revision"
              : `${report.revision_count} revision${report.revision_count > 1 ? "s" : ""}`}
          </p>
        </div>
        <p className="mt-2 max-w-3xl text-xs leading-relaxed text-slate-300">{report.summary}</p>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <CriticPanel report={report} />
          <RecommendedActionsPanel report={report} />
        </div>
      </div>

      <HypothesesSection report={report} evidenceById={evidenceById} />

      {report.rejected_citations.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-xs text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-medium">
              {report.rejected_citations.length} knowledge-base citation
              {report.rejected_citations.length > 1 ? "s were" : " was"} rejected.
            </p>
            <ul className="mt-1 space-y-0.5">
              {report.rejected_citations.map((citation, index) => (
                <li key={`${citation}-${index}`} className="break-words font-mono text-[11px]">
                  {citation}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <p className="text-[11px] leading-relaxed text-slate-600">{report.disclaimer}</p>
    </section>
  );
}

function CriticPanel({ report }: { report: NonNullable<InvestigationJob["report"]> }) {
  const review = report.critic_review;
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-3.5 w-3.5 text-warning" aria-hidden="true" />
        <h3 className="text-xs font-semibold text-white">Critic review</h3>
        {review.revision_required && (
          <StatusBadge label="Revision required" tone="warning" />
        )}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-400">{review.verification_outcome}</p>
      <ReviewList title="Issues found" items={review.issues_found} />
      <ReviewList title="Unsupported claims" items={review.unsupported_claims} />
      <ReviewList title="Alternative explanations" items={review.alternative_explanations} />
      {review.deterministic_findings.length > 0 && (
        <ReviewList title="Deterministic findings" items={review.deterministic_findings} tone="accent" />
      )}
      {review.excluded_evidence_reused.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-medium tracking-wide text-danger uppercase">
            Excluded evidence referenced
          </p>
          <ul className="mt-1.5 space-y-1">
            {review.excluded_evidence_reused.map((item, index) => (
              <li
                key={`${item}-${index}`}
                className={cn("rounded border px-2 py-1.5 text-[11px] leading-relaxed", ROW_TONES.danger)}
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ReviewList({
  title,
  items,
  tone = "neutral",
}: {
  title: string;
  items: string[];
  tone?: "neutral" | "accent";
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">{title}</p>
      <ul className="mt-1.5 space-y-1">
        {items.map((item, index) => (
          <li
            key={`${item}-${index}`}
            className={cn("rounded border px-2 py-1.5 text-[11px] leading-relaxed", ROW_TONES[tone])}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecommendedActionsPanel({
  report,
}: {
  report: NonNullable<InvestigationJob["report"]>;
}) {
  if (report.recommended_actions.length === 0) return null;
  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <div className="flex items-center gap-2">
        <ListChecks className="h-3.5 w-3.5 text-cyan-accent" aria-hidden="true" />
        <h3 className="text-xs font-semibold text-white">Recommended actions</h3>
      </div>
      <ol className="mt-3 space-y-2">
        {report.recommended_actions.map((action, index) => (
          <li key={`${action.action}-${index}`} className="text-xs">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-cyan-accent/10 text-[10px] font-semibold text-cyan-accent">
                {index + 1}
              </span>
              <div className="flex-1">
                <p className="font-medium text-slate-200">{action.action}</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{action.rationale}</p>
                {action.requires_human_approval && (
                  <StatusBadge
                    className="mt-1.5"
                    label="Requires human approval"
                    tone="warning"
                  />
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function HypothesesSection({
  report,
  evidenceById,
}: {
  report: NonNullable<InvestigationJob["report"]>;
  evidenceById: Map<string, { observation: string; source: string }>;
}) {
  if (report.hypotheses.length === 0) return null;
  return (
    <div className="rounded-lg border border-line bg-surface">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold text-white">Hypotheses</h2>
        <p className="mt-1 text-xs text-slate-400">
          Root-cause hypotheses ranked by the investigating agent and assessed by the critic.
        </p>
      </div>
      <ol className="divide-y divide-line/60">
        {report.hypotheses.map((hypothesis) => (
          <HypothesisRow key={hypothesis.hypothesis_id} hypothesis={hypothesis} evidenceById={evidenceById} />
        ))}
      </ol>
    </div>
  );
}

function HypothesisRow({
  hypothesis,
  evidenceById,
}: {
  hypothesis: Hypothesis;
  evidenceById: Map<string, { observation: string; source: string }>;
}) {
  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-cyan-accent/10 text-[10px] font-semibold text-cyan-accent">
          {hypothesis.hypothesis_id}
        </span>
        <h3 className="text-xs font-semibold text-slate-200">{hypothesis.title}</h3>
        <StatusBadge
          label={HYPOTHESIS_ASSESSMENT_LABELS[hypothesis.assessment]}
          tone={HYPOTHESIS_ASSESSMENT_TONE[hypothesis.assessment]}
        />
      </div>

      <p className="mt-2 max-w-3xl text-xs leading-relaxed text-slate-400">
        {hypothesis.description}
      </p>

      {hypothesis.supporting_evidence_ids.length > 0 && (
        <EvidenceChips
          label="Supporting evidence"
          icon={<CheckCircle2 className="h-3 w-3 text-success" aria-hidden="true" />}
          ids={hypothesis.supporting_evidence_ids}
          evidenceById={evidenceById}
        />
      )}

      {hypothesis.contradicting_evidence_ids.length > 0 && (
        <EvidenceChips
          label="Contradicting evidence"
          icon={<XCircle className="h-3 w-3 text-danger" aria-hidden="true" />}
          ids={hypothesis.contradicting_evidence_ids}
          evidenceById={evidenceById}
        />
      )}

      {hypothesis.missing_evidence.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">Missing evidence</p>
          <ul className="mt-1 space-y-0.5">
            {hypothesis.missing_evidence.map((item, index) => (
              <li key={`${item}-${index}`} className="text-[11px] text-slate-500">
                · {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {hypothesis.verification_steps.length > 0 && (
        <div className="mt-3 rounded-md border border-line bg-surface-raised px-3 py-2">
          <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">
            Verification steps
          </p>
          <ul className="mt-1 space-y-0.5">
            {hypothesis.verification_steps.map((step, index) => (
              <li key={`${step}-${index}`} className="text-[11px] leading-relaxed text-slate-400">
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

function EvidenceChips({
  label,
  icon,
  ids,
  evidenceById,
}: {
  label: string;
  icon: ReactNode;
  ids: string[];
  evidenceById: Map<string, { observation: string; source: string }>;
}) {
  return (
    <div className="mt-3">
      <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-slate-500 uppercase">
        {icon}
        {label}
      </p>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {ids.map((evidenceId) => {
          const record = evidenceById.get(evidenceId);
          return (
            <li
              key={evidenceId}
              title={
                record
                  ? `${record.source}: ${record.observation}`
                  : "Cited evidence is not in the catalog."
              }
              className={cn(
                "rounded border px-2 py-1 text-[11px]",
                record
                  ? "border-line bg-surface-raised text-slate-300"
                  : "border-warning/40 bg-warning/5 text-warning"
              )}
            >
              {evidenceId}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function EvidenceTable({
  evidence,
  active,
}: {
  evidence: EvidenceListResponse | null;
  active: boolean;
}) {
  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-white">Evidence catalog</h2>
          <p className="mt-1 text-xs text-slate-400">
            Deterministic measurements and retrieved knowledge driving the analysis.
          </p>
        </div>
        {evidence && (
          <span className="text-[11px] text-slate-500 tabular-nums">
            {evidence.total} record{evidence.total === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {!evidence || evidence.items.length === 0 ? (
        <p className={cn("px-5 py-8 text-center text-xs", active ? "text-slate-400" : "text-slate-500")}>
          {active ? "Evidence is being collected…" : "No evidence was collected."}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-xs">
            <caption className="sr-only">Evidence records collected for this investigation</caption>
            <thead>
              <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                <th scope="col" className="px-5 py-3 font-medium">Evidence ID</th>
                <th scope="col" className="px-3 py-3 font-medium">Type</th>
                <th scope="col" className="px-3 py-3 font-medium">Source</th>
                <th scope="col" className="px-3 py-3 font-medium">Observation</th>
                <th scope="col" className="px-3 py-3 font-medium">Value</th>
                <th scope="col" className="px-5 py-3 text-right font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {evidence.items.map((item) => (
                <tr key={item.evidence_id} className="border-b border-line/60 last:border-b-0 hover:bg-surface-raised">
                  <td className="px-5 py-3 font-mono text-[11px] text-cyan-accent">
                    {item.evidence_id}
                  </td>
                  <td className="px-3 py-3 text-slate-400">
                    {EVIDENCE_TYPE_LABELS[item.evidence_type] ?? item.evidence_type}
                  </td>
                  <td className="px-3 py-3 text-slate-300">{item.source}</td>
                  <td className="max-w-sm px-3 py-3">
                    <span className="line-clamp-2 text-slate-300">{item.observation}</span>
                  </td>
                  <td className="px-3 py-3 text-slate-400 tabular-nums">
                    {item.value !== null && item.value !== undefined
                      ? `${item.value}${item.units ? ` ${item.units}` : ""}`
                      : "—"}
                  </td>
                  <td className="px-5 py-3 text-right text-slate-500">
                    {formatDateTime(item.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}