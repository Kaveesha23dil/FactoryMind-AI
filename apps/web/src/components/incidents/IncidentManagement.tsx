"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  Loader2,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { getHealth, getIncidents, scanIncidents } from "@/lib/api";
import type { Severity } from "@/types/anomaly";
import type { ScanResponse } from "@/types/incident";
import type { BackendStatus } from "@/types/monitoring";
import { formatNumber } from "@/lib/format";
import DashboardHeader from "@/components/layout/DashboardHeader";
import StatCard from "@/components/dashboard/StatCard";
import ChartCard from "@/components/charts/ChartCard";
import IncidentTable from "@/components/incidents/IncidentTable";
import { KpiGridSkeleton } from "@/components/ui/Feedback";
import { cn } from "@/lib/format";

type ScanSeverity = Exclude<Severity, "normal">;

const SCAN_SEVERITIES: ScanSeverity[] = ["low", "medium", "high", "critical"];

interface IncidentCounts {
  total: number;
  open: number;
  under_review: number;
  resolved: number;
}

export default function IncidentManagement() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const [counts, setCounts] = useState<IncidentCounts | null>(null);
  const [loadingCounts, setLoadingCounts] = useState(true);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [tableRefreshToken, setTableRefreshToken] = useState(0);

  const [scanSeverity, setScanSeverity] = useState<ScanSeverity>("high");
  const [scanMax, setScanMax] = useState(25);
  const [scanDryRun, setScanDryRun] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  const loadCounts = useCallback(async () => {
    const [all, open, review, resolved] = await Promise.all([
      getIncidents({ limit: 1 }),
      getIncidents({ limit: 1, status: "open" }),
      getIncidents({ limit: 1, status: "under_review" }),
      getIncidents({ limit: 1, status: "resolved" }),
    ]);
    return {
      total: all.total,
      open: open.total,
      under_review: review.total,
      resolved: resolved.total,
    } satisfies IncidentCounts;
  }, []);

  useEffect(() => {
    let stale = false;
    getHealth()
      .then((health) => {
        if (stale) return;
        setBackendStatus(
          health.status === "healthy" ? "connected" : "unavailable"
        );
      })
      .catch(() => {
        if (stale) return;
        setBackendStatus("unavailable");
      });

    loadCounts()
      .then((result) => {
        if (stale) return;
        setCounts(result);
        setCountsError(null);
        setLoadingCounts(false);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setCountsError(
          err instanceof Error ? err.message : "Unable to load incident counts."
        );
        setLoadingCounts(false);
      });

    return () => {
      stale = true;
    };
  }, [loadCounts, tableRefreshToken]);

  const handleRefresh = useCallback(() => {
    setBackendStatus("checking");
    setRefreshing(true);
    setLoadingCounts(true);
    void getHealth()
      .then((health) =>
        setBackendStatus(
          health.status === "healthy" ? "connected" : "unavailable"
        )
      )
      .catch(() => setBackendStatus("unavailable"))
      .finally(() => setRefreshing(false));
    setTableRefreshToken((value) => value + 1);
  }, []);

  async function handleScan() {
    setScanning(true);
    setScanError(null);
    setScanResult(null);
    try {
      const result = await scanIncidents({
        min_severity: scanSeverity,
        max_incidents: scanMax,
        dry_run: scanDryRun,
      });
      setScanResult(result);
      if (!scanDryRun) {
        setTableRefreshToken((value) => value + 1);
      }
    } catch (err) {
      setScanError(
        err instanceof Error ? err.message : "The incident scan failed."
      );
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader
        title="Incidents"
        subtitle="Incident queue created from detected anomalies."
        datasetLabel="AI4I 2020 — Synthetic Dataset"
        backendStatus={backendStatus}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        <section aria-labelledby="incident-stats-heading">
          <h2
            id="incident-stats-heading"
            className="mb-3 text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase"
          >
            Incident Overview
          </h2>

          {loadingCounts ? (
            <KpiGridSkeleton />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Total Incidents"
                value={formatNumber(counts?.total ?? 0)}
                hint="All incidents in the store"
                icon={ShieldCheck}
                tone="accent"
              />
              <StatCard
                label="Open"
                value={formatNumber(counts?.open ?? 0)}
                hint="Awaiting review"
                icon={AlertTriangle}
                tone="danger"
              />
              <StatCard
                label="Under Review"
                value={formatNumber(counts?.under_review ?? 0)}
                hint="Being investigated"
                icon={Eye}
                tone="warning"
              />
              <StatCard
                label="Resolved"
                value={formatNumber(counts?.resolved ?? 0)}
                hint="Closed incidents"
                icon={CheckCircle2}
                tone="success"
              />
            </div>
          )}
          {countsError && (
            <p className="mt-2 text-xs text-danger">{countsError}</p>
          )}
        </section>

        <ChartCard
          title="Scan for incidents"
          description="Create incidents automatically from the highest-severity detected anomalies."
          note="The scan never uses ground-truth failure labels. It only considers detected anomaly severity and skips records that already have an active incident."
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <label
                  htmlFor="scan-severity"
                  className="mb-1 block text-[11px] text-slate-500"
                >
                  Minimum severity
                </label>
                <select
                  id="scan-severity"
                  value={scanSeverity}
                  onChange={(event) =>
                    setScanSeverity(event.target.value as ScanSeverity)
                  }
                  className="w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
                >
                  {SCAN_SEVERITIES.map((severity) => (
                    <option key={severity} value={severity}>
                      {severity.charAt(0).toUpperCase() + severity.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="scan-max"
                  className="mb-1 block text-[11px] text-slate-500"
                >
                  Max incidents
                </label>
                <input
                  id="scan-max"
                  type="number"
                  min={1}
                  max={200}
                  value={scanMax}
                  onChange={(event) => {
                    const parsed = Number(event.target.value);
                    setScanMax(
                      Number.isFinite(parsed)
                        ? Math.min(200, Math.max(1, Math.round(parsed)))
                        : 1
                    );
                  }}
                  className="w-full rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
                />
              </div>

              <div className="flex items-end">
                <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={scanDryRun}
                    onChange={(event) => setScanDryRun(event.target.checked)}
                    className="h-4 w-4 rounded border-line bg-surface-raised text-accent focus:ring-accent"
                  />
                  <span>Preview only (dry run)</span>
                </label>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleScan}
                disabled={scanning}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/15 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-accent/25 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                  scanning && "cursor-not-allowed opacity-60"
                )}
              >
                {scanning ? (
                  <Loader2
                    className="h-3.5 w-3.5 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <ScanSearch className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                {scanDryRun ? "Preview scan" : "Run scan"}
              </button>
              {scanError && (
                <p className="text-xs text-danger">{scanError}</p>
              )}
            </div>

            {scanResult && (
              <div className="rounded-md border border-line bg-surface-raised p-3 text-xs">
                <p className="font-medium text-slate-200">
                  {scanResult.dry_run ? "Preview results" : "Scan results"}
                </p>
                <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-slate-400 sm:grid-cols-3">
                  <li>
                    Candidates evaluated:{" "}
                    <span className="text-slate-200 tabular-nums">
                      {formatNumber(scanResult.candidates_evaluated)}
                    </span>
                  </li>
                  <li>
                    Incidents created:{" "}
                    <span className="text-slate-200 tabular-nums">
                      {formatNumber(scanResult.incidents_created)}
                    </span>
                  </li>
                  <li>
                    Skipped duplicates:{" "}
                    <span className="text-slate-200 tabular-nums">
                      {formatNumber(scanResult.incidents_skipped_duplicate)}
                    </span>
                  </li>
                </ul>
                {scanResult.created_incident_ids.length > 0 && (
                  <p className="mt-2 text-[11px] text-slate-500">
                    {scanResult.dry_run ? "Would create: " : "Created: "}
                    {scanResult.created_incident_ids.join(", ")}
                  </p>
                )}
              </div>
            )}
          </div>
        </ChartCard>

        <section aria-labelledby="incident-queue-heading">
          <h2 id="incident-queue-heading" className="sr-only">
            Incident queue
          </h2>
          <IncidentTable refreshToken={tableRefreshToken} />
        </section>

        <p className="pb-4 text-center text-[11px] text-slate-600">
          Incidents are application records derived from detected anomalies.
          They do not assert a confirmed equipment fault.
        </p>
      </div>
    </div>
  );
}
