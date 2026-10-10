"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BrainCircuit,
  ExternalLink,
  Loader2,
  Plus,
  X,
} from "lucide-react";
import { ApiError, createIncident, getAnomaly } from "@/lib/api";
import type { FeatureContribution } from "@/types/anomaly";
import Modal from "@/components/ui/Modal";
import StatusBadge from "@/components/ui/StatusBadge";
import FeatureContributionChart from "@/components/anomalies/FeatureContributionChart";
import {
  EmptyState,
  ErrorState,
} from "@/components/ui/Feedback";
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  SEVERITY_LABELS,
  SEVERITY_TONE,
} from "@/lib/severity";
import { cn, formatDecimal } from "@/lib/format";

interface AnomalyDetailsProps {
  recordId: number | null;
  onClose: () => void;
  onIncidentChange?: () => void;
}

function contributionRow(feature: FeatureContribution) {
  return (
    <tr
      key={feature.feature}
      className={cn(
        "border-b border-line/60 last:border-b-0",
        feature.is_anomalous && "bg-danger/5"
      )}
    >
      <td className="px-3 py-2 align-top">
        <span className="flex items-center gap-1.5 text-slate-200">
          {feature.is_anomalous && (
            <AlertTriangle
              className="h-3.5 w-3.5 text-danger"
              aria-hidden="true"
            />
          )}
          {feature.label}
        </span>
        <span className="text-[11px] text-slate-500">
          {feature.feature} · baseline: {feature.baseline_scope.replace("_", " ")}
        </span>
      </td>
      <td className="px-3 py-2 text-right text-slate-200 tabular-nums">
        {formatDecimal(feature.observed_value, 2)}
        <span className="ml-1 text-[11px] text-slate-500">{feature.unit}</span>
      </td>
      <td className="px-3 py-2 text-right text-slate-400 tabular-nums">
        {formatDecimal(feature.baseline_median, 2)}
      </td>
      <td
        className={cn(
          "px-3 py-2 text-right font-medium tabular-nums",
          feature.is_anomalous ? "text-danger" : "text-slate-300"
        )}
      >
        {formatDecimal(feature.robust_zscore, 2)}
      </td>
      <td className="px-3 py-2 text-right text-slate-400">
        {feature.direction === "high" ? "High" : "Low"}
      </td>
    </tr>
  );
}

export default function AnomalyDetails({
  recordId,
  onClose,
  onIncidentChange,
}: AnomalyDetailsProps) {
  const [detail, setDetail] = useState<Awaited<
    ReturnType<typeof getAnomaly>
  > | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [justCreatedId, setJustCreatedId] = useState<string | null>(null);

  useEffect(() => {
    if (recordId == null) return;
    let stale = false;
    getAnomaly(recordId)
      .then((response) => {
        if (stale) return;
        setDetail(response);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setError(
          err instanceof Error ? err.message : "Unable to load anomaly evidence."
        );
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [recordId]);



  if (recordId == null) return null;

  async function handleCreateIncident() {
    if (recordId == null) return;
    setCreating(true);
    setActionError(null);
    try {
      const incident = await createIncident(recordId);
      setJustCreatedId(incident.incident_id);
      setDetail((current) =>
        current
          ? {
              ...current,
              incident_status: incident.status,
              incident_id: incident.incident_id,
            }
          : current
      );
      onIncidentChange?.();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setActionError("An active incident already exists for this record.");
        try {
          const refreshed = await getAnomaly(recordId);
          setDetail(refreshed);
          onIncidentChange?.();
        } catch {
          /* ignore refresh failure */
        }
      } else {
        setActionError(
          err instanceof Error ? err.message : "Could not create the incident."
        );
      }
    } finally {
      setCreating(false);
    }
  }

  return (
    <Modal open={true} onClose={onClose} labelledBy="anomaly-details-title"
      className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-t-lg border border-line bg-surface shadow-2xl outline-none sm:rounded-lg">
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-line bg-surface px-5 py-4">
          <div>
            <p className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Anomaly evidence
            </p>
            <h2
              id="anomaly-details-title"
              className="mt-1 text-lg font-semibold text-white"
            >
              Record #{recordId}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {detail && (
              <StatusBadge
                label={`${SEVERITY_LABELS[detail.severity]} severity`}
                tone={SEVERITY_TONE[detail.severity]}
                dot
              />
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close anomaly evidence"
              className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-surface-raised hover:text-white focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="space-y-4 p-5">
            <div className="h-24 animate-pulse rounded-md bg-surface-raised" />
            <div className="h-64 animate-pulse rounded-md bg-surface-raised" />
          </div>
        ) : error ? (
          <ErrorState title="Anomaly evidence unavailable" message={error} />
        ) : detail ? (
          <div className="space-y-5 px-5 py-5">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <p className="text-[11px] text-slate-500">Anomaly score</p>
                <p className="mt-0.5 text-lg font-semibold text-white tabular-nums">
                  {formatDecimal(detail.anomaly_score, 2)}
                </p>
                <p className="text-[11px] text-slate-500">
                  Threshold {formatDecimal(detail.threshold, 2)}
                </p>
              </div>
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <p className="text-[11px] text-slate-500">Detection algorithm</p>
                <p className="mt-0.5 font-mono text-sm text-cyan-accent">
                  {detail.algorithm}
                </p>
                <p className="text-[11px] text-slate-500">
                  Feature z-limit {formatDecimal(detail.feature_z_threshold, 2)}
                </p>
              </div>
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <p className="text-[11px] text-slate-500">Machine</p>
                <p className="mt-0.5 text-sm font-medium text-white">
                  {detail.product_id}
                </p>
                <p className="text-[11px] text-slate-500">
                  Type {detail.machine_type}
                </p>
              </div>
            </div>

            <div className="rounded-md border border-line bg-surface-raised p-4">
              <p className="text-xs font-medium text-slate-300">
                Algorithm finding vs dataset ground truth
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-4 text-xs">
                <span className="flex items-center gap-2">
                  <StatusBadge
                    label={
                      detail.is_anomaly
                        ? `Algorithm: ${SEVERITY_LABELS[detail.severity]} anomaly`
                        : "Algorithm: normal"
                    }
                    tone={SEVERITY_TONE[detail.severity]}
                    dot
                  />
                </span>
                <span className="flex items-center gap-2">
                  <StatusBadge
                    label={
                      detail.ground_truth_failure
                        ? "Dataset ground truth: failure"
                        : "Dataset ground truth: no failure"
                    }
                    tone={detail.ground_truth_failure ? "danger" : "success"}
                  />
                </span>
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                These are different things. The severity above is an
                application-defined anomaly level from the detection algorithm,
                not a calibrated failure probability and not an official
                equipment safety class. The ground-truth label is recorded in
                the AI4I dataset and was never used as a detection input.
              </p>
            </div>

            <section>
              <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
                Feature-level contributions
              </h3>
              <p className="mt-1 text-xs text-slate-400">
                Observed sample values compared with the training baseline
                (median). Highlighted rows exceed the per-feature z-score limit.
              </p>
              <div className="mt-3 overflow-x-auto rounded-md border border-line">
                <table className="w-full min-w-[620px] text-left text-xs">
                  <thead>
                    <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                      <th scope="col" className="px-3 py-2 font-medium">
                        Feature
                      </th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">
                        Observed
                      </th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">
                        Baseline median
                      </th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">
                        z-score
                      </th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">
                        Direction
                      </th>
                    </tr>
                  </thead>
                  <tbody>{detail.features.map(contributionRow)}</tbody>
                </table>
              </div>
            </section>

            <section>
              <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
                Contribution chart
              </h3>
              <p className="mt-1 text-xs text-slate-400">
                Signed robust z-score per feature (unitless). Dashed lines mark
                the per-feature anomaly limit.
              </p>
              <FeatureContributionChart
                features={detail.features}
                featureZThreshold={detail.feature_z_threshold}
              />
            </section>

            <section>
              <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
                Detection explanations
              </h3>
              {detail.anomalous_features.length === 0 ? (
                <EmptyState
                  title="No feature exceeded the limit"
                  description="No individual feature crossed the configured robust z-score limit for this record."
                />
              ) : (
                <ul className="mt-3 space-y-2">
                  {detail.anomalous_features.map((feature) => (
                    <li
                      key={feature.feature}
                      className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs leading-relaxed text-slate-300"
                    >
                      {feature.explanation}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-md border border-dashed border-line p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <Plus className="h-4 w-4 text-accent" aria-hidden="true" />
                    Incident management
                  </p>
                  {detail.incident_id ? (
                    <p className="mt-1 text-xs text-slate-500">
                      An active incident exists for this record.
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-slate-500">
                      Create an incident to track this detected anomaly.
                    </p>
                  )}
                  {justCreatedId && (
                    <p className="mt-1 text-xs text-success">
                      Created incident {justCreatedId}.
                    </p>
                  )}
                  {actionError && (
                    <p className="mt-1 text-xs text-warning">{actionError}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {detail.incident_id ? (
                    <>
                      <StatusBadge
                        label={
                          detail.incident_status
                            ? INCIDENT_STATUS_LABELS[detail.incident_status]
                            : "Incident"
                        }
                        tone={
                          detail.incident_status
                            ? INCIDENT_STATUS_TONE[detail.incident_status]
                            : "neutral"
                        }
                        dot
                      />
                      <Link
                        href={`/incidents/${detail.incident_id}`}
                        className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-2 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        View incident
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </Link>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={handleCreateIncident}
                      disabled={creating}
                      className="inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/15 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-accent/25 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {creating ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                      ) : (
                        <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      Create incident
                    </button>
                  )}
                </div>
              </div>
            </section>

            <section className="rounded-md border border-dashed border-line p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="flex items-center gap-2 text-sm font-medium text-slate-300">
                    <BrainCircuit className="h-4 w-4 text-accent" aria-hidden="true" />
                    Investigate with AI
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Gemini-powered, evidence-based root-cause investigation is
                    planned for the next phase.
                  </p>
                </div>
                <button
                  type="button"
                  disabled
                  aria-disabled="true"
                  className="shrink-0 cursor-not-allowed rounded-md border border-line bg-surface-raised px-3 py-2 text-xs font-medium text-slate-500"
                >
                  Coming in Step 4
                </button>
              </div>
            </section>
          </div>
        ) : null}
    </Modal>
  );
}
