"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FlaskConical,
  GitCompareArrows,
  Loader2,
  MinusCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import {
  createCounterfactual,
  getInvestigationCounterfactuals,
} from "@/lib/api";
import type {
  CounterfactualListResponse,
  CounterfactualScenario,
  HypothesisChange,
} from "@/types/counterfactual";
import type { EvidenceListResponse } from "@/types/investigation";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/ui/Feedback";
import {
  COUNTERFACTUAL_STATUS_LABELS,
  COUNTERFACTUAL_STATUS_TONE,
  EVIDENCE_TYPE_LABELS,
  EXCLUDABLE_EVIDENCE_TYPES,
} from "@/lib/investigations";
import { cn, formatDateTime } from "@/lib/format";

const POLL_INTERVAL_MS = 2500;

interface CounterfactualPanelProps {
  investigationId: string;
  evidence: EvidenceListResponse | null;
}

export default function CounterfactualPanel({
  investigationId,
  evidence,
}: CounterfactualPanelProps) {
  const [list, setList] = useState<CounterfactualListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const [selected, setSelected] = useState<CounterfactualScenario | null>(null);

  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set());
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const excludable = useMemo(
    () =>
      (evidence?.items ?? []).filter((item) =>
        EXCLUDABLE_EVIDENCE_TYPES.includes(item.evidence_type)
      ),
    [evidence]
  );

  useEffect(() => {
    let stale = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    (async () => {
      try {
        const next = await getInvestigationCounterfactuals(investigationId);
        if (stale) return;
        setList(next);
        setLoadError(null);
        setLoading(false);
        setSelected((current) => {
          if (!current) return current;
          return next.items.find((item) => item.scenario_id === current.scenario_id) ?? current;
        });
        if (next.items.some((item) => item.status === "running")) {
          timer = setTimeout(() => setTick((value) => value + 1), POLL_INTERVAL_MS);
        }
      } catch (err) {
        if (stale) return;
        setLoadError(
          err instanceof Error
            ? err.message
            : "Unexpected error while loading counterfactual scenarios."
        );
        setLoading(false);
      }
    })();

    return () => {
      stale = true;
      if (timer) clearTimeout(timer);
    };
  }, [investigationId, tick]);

  const toggle = useCallback((evidenceId: string) => {
    setExcludedIds((current) => {
      const next = new Set(current);
      if (next.has(evidenceId)) next.delete(evidenceId);
      else next.add(evidenceId);
      return next;
    });
  }, []);

  const submit = async () => {
    if (excludedIds.size === 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createCounterfactual(
        investigationId,
        [...excludedIds],
        rationale.trim() || null
      );
      setSelected(created);
      setExcludedIds(new Set());
      setRationale("");
      setTick((value) => value + 1);
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "The scenario could not be created."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = excludedIds.size > 0 && !submitting && excludable.length > 0;

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-line bg-surface px-5 py-4">
        <div className="flex items-start gap-3">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-cyan-accent" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold text-white">Counterfactual investigation</h2>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-400">
              Remove selected evidence and re-run the full multi-agent pipeline against a
              restricted context. The original investigation is never modified. The revised
              anomaly score is a deterministic recomputation, not a model estimate.
            </p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <section className="rounded-lg border border-line bg-surface">
          <div className="flex items-center justify-between gap-2 border-b border-line px-5 py-4">
            <div>
              <h3 className="text-sm font-semibold text-white">Exclude evidence</h3>
              <p className="mt-1 text-xs text-slate-400">
                Select the records to withhold, then run the counterfactual.
              </p>
            </div>
            <span className="text-[11px] text-slate-500 tabular-nums">
              {excludedIds.size} selected
            </span>
          </div>

          {evidence && evidence.items.length > 0 ? (
            <>
              <div className="flex items-center justify-between border-b border-line/60 px-5 py-2 text-[11px]">
                <button
                  type="button"
                  onClick={() => setExcludedIds(new Set(excludable.map((item) => item.evidence_id)))}
                  className="text-cyan-accent underline-offset-2 hover:underline"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={() => setExcludedIds(new Set())}
                  className="text-slate-400 underline-offset-2 hover:text-slate-200 hover:underline"
                >
                  Clear
                </button>
              </div>
              <ul className="max-h-[340px] divide-y divide-line/60 overflow-y-auto">
                {excludable.map((item) => {
                  const checked = excludedIds.has(item.evidence_id);
                  return (
                    <li key={item.evidence_id}>
                      <label
                        className={cn(
                          "flex cursor-pointer items-start gap-3 px-5 py-3 transition-colors hover:bg-surface-raised",
                          checked && "bg-danger/5"
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(item.evidence_id)}
                          className="mt-0.5 h-3.5 w-3.5 rounded border-line bg-surface accent-danger"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-[11px] text-cyan-accent">
                              {item.evidence_id}
                            </span>
                            <span className="text-[10px] text-slate-500">
                              {EVIDENCE_TYPE_LABELS[item.evidence_type] ?? item.evidence_type}
                            </span>
                          </span>
                          <span className="mt-1 block line-clamp-2 text-[11px] text-slate-400">
                            {item.observation}
                          </span>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              <div className="border-t border-line px-5 py-4">
                <label className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">
                  Rationale (optional)
                </label>
                <textarea
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  rows={2}
                  placeholder="Why are these records being withheld?"
                  className="mt-1.5 w-full resize-none rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                />
                {submitError && (
                  <p className="mt-2 flex items-start gap-1.5 text-[11px] text-danger">
                    <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                    {submitError}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={!canSubmit}
                  className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent/90 focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {submitting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <FlaskConical className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  {submitting ? "Running counterfactual…" : "Run counterfactual"}
                </button>
              </div>
            </>
          ) : (
            <EmptyState
              title="No excludable evidence"
              description="Evidence must be collected before a counterfactual can be run."
            />
          )}
        </section>

        <div className="space-y-6">
          <ScenarioHistory
            list={list}
            loading={loading}
            error={loadError}
            selectedId={selected?.scenario_id ?? null}
            onSelect={setSelected}
            onRefresh={() => setTick((value) => value + 1)}
          />

          {selected && <ScenarioDetail scenario={selected} />}
        </div>
      </div>
    </div>
  );
}

function ScenarioHistory({
  list,
  loading,
  error,
  selectedId,
  onSelect,
  onRefresh,
}: {
  list: CounterfactualListResponse | null;
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (scenario: CounterfactualScenario) => void;
  onRefresh: () => void;
}) {
  if (loading && !list) return <CardSkeleton />;
  if (error) {
    return (
      <section className="rounded-lg border border-line bg-surface">
        <ErrorState title="Could not load scenarios" message={error} onRetry={onRefresh} />
      </section>
    );
  }

  const items = list?.items ?? [];

  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-line px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Scenario history</h3>
          <p className="mt-1 text-xs text-slate-400">
            {items.length} counterfactual scenario{items.length === 1 ? "" : "s"} for this investigation.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          aria-label="Refresh scenarios"
          className="rounded-md border border-line bg-surface-raised p-2 text-slate-300 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      {items.length === 0 ? (
        <EmptyState
          title="No scenarios yet"
          description="Exclude some evidence on the left to create the first counterfactual revision."
        />
      ) : (
        <ul className="divide-y divide-line/60">
          {items.map((scenario) => (
            <li key={scenario.scenario_id}>
              <button
                type="button"
                onClick={() => onSelect(scenario)}
                className={cn(
                  "flex w-full flex-col gap-2 px-5 py-4 text-left transition-colors hover:bg-surface-raised",
                  scenario.scenario_id === selectedId && "bg-surface-raised"
                )}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] text-cyan-accent">
                    {scenario.scenario_id}
                  </span>
                  <StatusBadge
                    label={COUNTERFACTUAL_STATUS_LABELS[scenario.status]}
                    tone={COUNTERFACTUAL_STATUS_TONE[scenario.status]}
                    dot
                  />
                  <span className="text-[11px] text-slate-500 tabular-nums">
                    {scenario.excluded_evidence_ids.length} excluded
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  {scenario.rationale ??
                    "No rationale provided."}
                </p>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
                  <span>{formatDateTime(scenario.created_at)}</span>
                  {scenario.excluded_feature_keys.length > 0 && (
                    <span>
                      features: {scenario.excluded_feature_keys.join(", ")}
                    </span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ScenarioDetail({ scenario }: { scenario: CounterfactualScenario }) {
  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-4">
        <div className="flex items-center gap-2">
          <GitCompareArrows className="h-4 w-4 text-cyan-accent" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-white">Comparison</h3>
          <StatusBadge
            label={COUNTERFACTUAL_STATUS_LABELS[scenario.status]}
            tone={COUNTERFACTUAL_STATUS_TONE[scenario.status]}
            dot
          />
        </div>
        {scenario.revised_investigation_id && (
          <span className="text-[11px] text-slate-500">
            Revised run{" "}
            <span className="font-mono text-slate-300">{scenario.revised_investigation_id}</span>
          </span>
        )}
      </div>

      {scenario.status === "running" && (
        <div className="flex items-center gap-2 px-5 py-8 text-xs text-cyan-accent">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          The revised investigation is still running…
        </div>
      )}

      {scenario.status === "failed" && (
        <div className="px-5 py-5">
          <div className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">The counterfactual could not be completed.</p>
              {scenario.error && <p className="mt-0.5 break-words">{scenario.error}</p>}
            </div>
          </div>
        </div>
      )}

      {scenario.status === "completed" && scenario.comparison && (
        <ComparisonBody comparison={scenario.comparison} />
      )}

      <div className="border-t border-line px-5 py-4">
        <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
          Dependency trace
        </p>
        {scenario.dependency_trace.length === 0 ? (
          <p className="mt-1.5 text-[11px] text-slate-500">
            No derived features were affected by this exclusion set.
          </p>
        ) : (
          <ul className="mt-1.5 space-y-1.5">
            {scenario.dependency_trace.map((entry) => (
              <li
                key={entry.feature}
                className="flex flex-wrap items-center gap-2 rounded border border-line bg-surface-raised px-2.5 py-1.5 text-[11px]"
              >
                <span className="font-medium text-slate-200">{entry.label}</span>
                <StatusBadge
                  label={entry.reason === "derived" ? "Derived" : "Direct"}
                  tone={entry.reason === "derived" ? "warning" : "neutral"}
                />
                {entry.evidence_ids.length > 0 && (
                  <span className="font-mono text-[10px] text-slate-500">
                    {entry.evidence_ids.join(", ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ComparisonBody({
  comparison,
}: {
  comparison: NonNullable<CounterfactualScenario["comparison"]>;
}) {
  const { anomaly } = comparison;
  return (
    <div className="space-y-5 px-5 py-5">
      <div className="rounded-md border border-cyan-accent/20 bg-cyan-accent/5 px-3 py-2.5">
        <p className="text-xs leading-relaxed text-slate-200">{comparison.summary}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <MetricCard
          label="Anomaly score"
          original={anomaly.original_score}
          revised={anomaly.revised_score}
        />
        <MetricCard
          label="Severity"
          original={anomaly.original_severity}
          revised={anomaly.revised_severity}
          raw
        />
        <div className="rounded-md border border-line bg-surface-raised p-3">
          <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
            Restricted context
          </p>
          <p className="mt-1 text-xs text-slate-300">
            {anomaly.retained_feature_count} feature{anomaly.retained_feature_count === 1 ? "" : "s"} retained
          </p>
          <p className="mt-1 text-[10px] text-slate-500">
            threshold {anomaly.threshold} · deterministic recomputation
          </p>
        </div>
      </div>

      {anomaly.excluded_feature_keys.length > 0 && (
        <div>
          <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
            Features removed
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1.5">
            {anomaly.excluded_feature_keys.map((key) => (
              <li
                key={key}
                className="rounded border border-danger/30 bg-danger/5 px-2 py-1 font-mono text-[10px] text-danger"
              >
                {key}
              </li>
            ))}
          </ul>
        </div>
      )}

      <HypothesisGroup title="Removed hypotheses" changes={comparison.removed_hypotheses} tone="danger" />
      <HypothesisGroup title="Added hypotheses" changes={comparison.added_hypotheses} tone="success" />
      <HypothesisGroup title="Retained hypotheses" changes={comparison.retained_hypotheses} tone="neutral" />

      {comparison.assessment_shifts.length > 0 && (
        <div>
          <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">
            Assessment shifts
          </p>
          <ul className="mt-1.5 space-y-1.5">
            {comparison.assessment_shifts.map((shift) => (
              <li
                key={shift.title}
                className="flex flex-wrap items-center gap-2 rounded border border-line bg-surface-raised px-2.5 py-1.5 text-[11px]"
              >
                <span className="text-slate-200">{shift.title}</span>
                <span className="text-slate-500">{shift.original_assessment}</span>
                <ArrowRight className="h-3 w-3 text-slate-600" aria-hidden="true" />
                <span className="text-cyan-accent">{shift.revised_assessment}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <StringDiff
        title="New contradictions"
        items={comparison.new_contradictions}
        tone="danger"
      />
      <StringDiff
        title="Resolved contradictions"
        items={comparison.removed_contradictions}
        tone="success"
      />
      <StringDiff
        title="New missing evidence"
        items={comparison.new_missing_evidence}
        tone="warning"
      />
      <StringDiff
        title="Recommendations added"
        items={comparison.recommendation_diff.added}
        tone="success"
      />
      <StringDiff
        title="Recommendations removed"
        items={comparison.recommendation_diff.removed}
        tone="danger"
      />
      <StringDiff title="Notes" items={comparison.notes} tone="neutral" />
    </div>
  );
}

function MetricCard({
  label,
  original,
  revised,
  raw = false,
}: {
  label: string;
  original: number | string | null;
  revised: number | string | null;
  raw?: boolean;
}) {
  const format = (value: number | string | null) => {
    if (value === null || value === undefined) return "—";
    if (raw || typeof value === "string") return String(value);
    return value.toFixed(4);
  };
  const changed = original !== revised;
  return (
    <div className="rounded-md border border-line bg-surface-raised p-3">
      <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{label}</p>
      <div className="mt-1 flex items-center gap-2 text-xs">
        <span className="font-mono text-slate-400 tabular-nums">{format(original)}</span>
        <ArrowRight className="h-3 w-3 text-slate-600" aria-hidden="true" />
        <span
          className={cn(
            "font-mono tabular-nums",
            changed ? "font-semibold text-cyan-accent" : "text-slate-300"
          )}
        >
          {format(revised)}
        </span>
      </div>
    </div>
  );
}

function HypothesisGroup({
  title,
  changes,
  tone,
}: {
  title: string;
  changes: HypothesisChange[];
  tone: "neutral" | "success" | "danger";
}) {
  if (changes.length === 0) return null;
  const Icon = tone === "danger" ? MinusCircle : tone === "success" ? CheckCircle2 : GitCompareArrows;
  const iconColor =
    tone === "danger" ? "text-danger" : tone === "success" ? "text-success" : "text-slate-400";
  return (
    <div>
      <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{title}</p>
      <ul className="mt-1.5 space-y-1.5">
        {changes.map((change, index) => (
          <li
            key={`${change.title}-${index}`}
            className="flex items-start gap-2 rounded border border-line bg-surface-raised px-2.5 py-2 text-[11px]"
          >
            <Icon className={cn("mt-0.5 h-3 w-3 shrink-0", iconColor)} aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-slate-200">{change.title}</p>
              {(change.original_assessment || change.revised_assessment) && (
                <p className="mt-0.5 text-slate-500">
                  {change.original_assessment ?? "—"} → {change.revised_assessment ?? "—"}
                </p>
              )}
              {change.note && <p className="mt-0.5 text-[10px] text-slate-500">{change.note}</p>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StringDiff({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "neutral" | "success" | "danger" | "warning";
}) {
  if (items.length === 0) return null;
  const colors: Record<typeof tone, string> = {
    neutral: "border-line bg-surface-raised text-slate-300",
    success: "border-success/30 bg-success/5 text-success",
    danger: "border-danger/30 bg-danger/5 text-danger",
    warning: "border-warning/30 bg-warning/5 text-warning",
  };
  return (
    <div>
      <p className="text-[10px] font-medium tracking-wide text-slate-500 uppercase">{title}</p>
      <ul className="mt-1.5 space-y-1">
        {items.map((item, index) => (
          <li
            key={`${item}-${index}`}
            className={cn("rounded border px-2.5 py-1.5 text-[11px] leading-relaxed", colors[tone])}
          >
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}