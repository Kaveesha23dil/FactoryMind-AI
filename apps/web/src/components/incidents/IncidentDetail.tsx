"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BrainCircuit } from "lucide-react";
import { getIncident } from "@/lib/api";
import type { Incident } from "@/types/incident";
import type { FeatureContribution } from "@/types/anomaly";
import StatusBadge from "@/components/ui/StatusBadge";
import FeatureContributionChart from "@/components/anomalies/FeatureContributionChart";
import IncidentStatusControl from "@/components/incidents/IncidentStatusControl";
import IncidentTimeline from "@/components/incidents/IncidentTimeline";
import {
  EmptyState,
  ErrorState,
} from "@/components/ui/Feedback";
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  SEVERITY_LABELS,
  SEVERITY_TONE,
  featureLabel,
} from "@/lib/severity";
import { cn, formatDateTime, formatDecimal } from "@/lib/format";

interface IncidentDetailProps {
  incidentId: string;
}

function formatMeasurement(value: unknown): string {
  if (typeof value === "number") {
    return formatDecimal(value, 2);
  }
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function evidenceRow(feature: FeatureContribution) {
  return (
    <tr
      key={feature.feature}
      className={cn(
        "border-b border-line/60 last:border-b-0",
        feature.is_anomalous && "bg-danger/5"
      )}
    >
      <td className="px-3 py-2 text-slate-300">{feature.label}</td>
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

export default function IncidentDetail({ incidentId }: IncidentDetailProps) {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    getIncident(incidentId)
      .then((response) => {
        if (stale) return;
        setIncident(response);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setIncident(null);
        setError(
          err instanceof Error ? err.message : "Unable to load the incident."
        );
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [incidentId]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-col gap-4 border-b border-line bg-surface/40 px-4 py-5 sm:px-6 xl:px-8">
        <Link
          href="/incidents"
          className="inline-flex w-fit items-center gap-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-200 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Back to incidents
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Incident
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-white sm:text-2xl">
              {incidentId}
            </h1>
          </div>
          {incident && (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                label={`${SEVERITY_LABELS[incident.severity]} severity`}
                tone={SEVERITY_TONE[incident.severity]}
                dot
              />
              <StatusBadge
                label={INCIDENT_STATUS_LABELS[incident.status]}
                tone={INCIDENT_STATUS_TONE[incident.status]}
                dot
              />
            </div>
          )}
        </div>
      </header>

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        {loading ? (
          <div className="space-y-4">
            <div className="h-28 animate-pulse rounded-lg bg-surface" />
            <div className="h-64 animate-pulse rounded-lg bg-surface" />
          </div>
        ) : error ? (
          <div className="rounded-lg border border-line bg-surface">
            <ErrorState
              title="Incident unavailable"
              message={error}
            />
          </div>
        ) : incident ? (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="space-y-6 xl:col-span-2">
              <section className="rounded-lg border border-line bg-surface p-5">
                <h2 className="text-sm font-semibold text-white">
                  Incident metadata
                </h2>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Record ID</dt>
                    <dd className="mt-0.5 font-medium text-white tabular-nums">
                      {incident.record_id}
                    </dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Product ID</dt>
                    <dd className="mt-0.5 font-medium text-white">
                      {incident.product_id}
                    </dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Machine type</dt>
                    <dd className="mt-0.5 font-medium text-white">
                      {incident.machine_type}
                    </dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Algorithm</dt>
                    <dd className="mt-0.5 font-mono text-xs text-cyan-accent">
                      {incident.algorithm}
                    </dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Created</dt>
                    <dd className="mt-0.5 text-xs text-white">
                      {formatDateTime(incident.created_at)}
                    </dd>
                  </div>
                  <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                    <dt className="text-[11px] text-slate-500">Last updated</dt>
                    <dd className="mt-0.5 text-xs text-white">
                      {formatDateTime(incident.updated_at)}
                    </dd>
                  </div>
                </dl>
                {incident.note && (
                  <p className="mt-3 rounded-md border border-line bg-surface-raised px-3 py-2 text-xs leading-relaxed text-slate-300">
                    {incident.note}
                  </p>
                )}
              </section>

              <section className="rounded-lg border border-line bg-surface p-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-sm font-semibold text-white">
                    Anomaly evidence
                  </h2>
                  <p className="text-xs text-slate-400">
                    Anomaly score{" "}
                    <span className="font-medium text-white tabular-nums">
                      {formatDecimal(incident.anomaly_score, 2)}
                    </span>
                  </p>
                </div>
                <div className="mt-4 overflow-x-auto rounded-md border border-line">
                  <table className="w-full min-w-[620px] text-left text-xs">
                    <caption className="sr-only">
                      Feature-level evidence for this incident
                    </caption>
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
                    <tbody>{incident.evidence.map(evidenceRow)}</tbody>
                  </table>
                </div>

                {incident.evidence.length > 0 && incident.detection_config && (
                  <div className="mt-4">
                    <FeatureContributionChart
                      features={incident.evidence}
                      featureZThreshold={incident.detection_config.feature_z_threshold}
                    />
                  </div>
                )}

                {incident.explanations.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {incident.explanations.map((explanation, index) => (
                      <li
                        key={index}
                        className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs leading-relaxed text-slate-300"
                      >
                        {explanation}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-lg border border-line bg-surface p-5">
                <h2 className="text-sm font-semibold text-white">
                  Source observation
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Sensor values for the dataset observation that triggered this
                  incident.
                </p>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                  {Object.entries(incident.source_measurements).map(
                    ([key, value]) => (
                      <div
                        key={key}
                        className="flex flex-col gap-0.5 rounded-md border border-line bg-surface-raised px-3 py-2"
                      >
                        <dt className="text-[11px] text-slate-500">
                          {featureLabel(key)}
                        </dt>
                        <dd className="font-medium text-white tabular-nums">
                          {formatMeasurement(value)}
                        </dd>
                      </div>
                    )
                  )}
                </dl>
              </section>

              <section className="rounded-lg border border-dashed border-line p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="flex items-center gap-2 text-sm font-medium text-slate-300">
                      <BrainCircuit
                        className="h-4 w-4 text-accent"
                        aria-hidden="true"
                      />
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

            <div className="space-y-6">
              <IncidentStatusControl
                incident={incident}
                onUpdated={setIncident}
              />

              <section className="rounded-lg border border-line bg-surface p-5">
                <h2 className="text-sm font-semibold text-white">
                  Status history
                </h2>
                <div className="mt-4">
                  <IncidentTimeline entries={incident.timeline} />
                </div>
              </section>
            </div>
          </div>
        ) : (
          <EmptyState
            title="Incident not found"
            description="The requested incident could not be found in the incident store."
          />
        )}
      </div>
    </div>
  );
}
