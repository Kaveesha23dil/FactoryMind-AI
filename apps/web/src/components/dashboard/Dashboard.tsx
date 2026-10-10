"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Percent,
} from "lucide-react";
import {
  getDatasetSummary,
  getHealth,
  getTelemetry,
} from "@/lib/api";
import type {
  BackendStatus,
  DatasetSummary,
  TelemetryRecord,
} from "@/types/monitoring";
import { formatNumber, formatPercent } from "@/lib/format";
import DashboardHeader from "@/components/layout/DashboardHeader";
import StatCard from "@/components/dashboard/StatCard";
import ChartCard from "@/components/charts/ChartCard";
import TemperatureChart from "@/components/charts/TemperatureChart";
import SensorMetrics from "@/components/charts/SensorMetrics";
import FailureCategories from "@/components/charts/FailureCategories";
import TelemetryTable from "@/components/telemetry/TelemetryTable";
import {
  CardSkeleton,
  ChartSkeleton,
  ErrorState,
  KpiGridSkeleton,
} from "@/components/ui/Feedback";

const CHART_SAMPLE_COUNT = 300;

export default function Dashboard() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [chartRecords, setChartRecords] = useState<TelemetryRecord[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tableRefreshToken, setTableRefreshToken] = useState(0);

  async function fetchDashboardData() {
    return Promise.allSettled([
      getHealth(),
      getDatasetSummary(),
      getTelemetry({ limit: CHART_SAMPLE_COUNT, offset: 0 }),
    ]);
  }

  const applyResults = useCallback(
    (
      results: Awaited<ReturnType<typeof fetchDashboardData>>
    ) => {
      const [healthResult, summaryResult, telemetryResult] = results;

      if (healthResult.status === "fulfilled") {
        setBackendStatus(
          healthResult.value.status === "healthy" ? "connected" : "unavailable"
        );
      } else {
        setBackendStatus("unavailable");
      }

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
        setLoadError(null);
      } else {
        const reason = summaryResult.reason;
        setLoadError(
          reason instanceof Error
            ? reason.message
            : "Unable to load dataset summary."
        );
      }

      if (telemetryResult.status === "fulfilled") {
        setChartRecords(telemetryResult.value.records);
        setChartError(null);
      } else {
        const reason = telemetryResult.reason;
        setChartError(
          reason instanceof Error
            ? reason.message
            : "Unable to load sensor samples."
        );
      }

      setInitialLoading(false);
    },
    []
  );

  useEffect(() => {
    let stale = false;
    void fetchDashboardData().then((results) => {
      if (stale) return;
      applyResults(results);
    });
    return () => {
      stale = true;
    };
  }, [applyResults]);

  const handleRefresh = useCallback(() => {
    setBackendStatus("checking");
    setLoadError(null);
    setChartError(null);
    setRefreshing(true);
    void fetchDashboardData()
      .then((results) => {
        setInitialLoading(false);
        applyResults(results);
      })
      .finally(() => setRefreshing(false));
    setTableRefreshToken((value) => value + 1);
  }, [applyResults]);

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader
        title="Machine Monitoring"
        subtitle="Industrial equipment monitoring and operational insights."
        datasetLabel="AI4I 2020 — Synthetic Dataset"
        backendStatus={backendStatus}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        <section aria-labelledby="overview-stats-heading">
          <h2
            id="overview-stats-heading"
            className="mb-3 text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase"
          >
            Dataset Overview
          </h2>

          {initialLoading ? (
            <KpiGridSkeleton />
          ) : loadError && !summary ? (
            <div className="rounded-lg border border-line bg-surface">
              <ErrorState
                title="Dataset summary unavailable"
                message={loadError}
                onRetry={handleRefresh}
              />
            </div>
          ) : summary ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Total Records"
                value={formatNumber(summary.record_count)}
                hint="Rows in the AI4I 2020 dataset"
                icon={Database}
                tone="accent"
              />
              <StatCard
                label="Normal Records"
                value={formatNumber(summary.normal_count)}
                hint="Records with no failure recorded"
                icon={CheckCircle2}
                tone="success"
              />
              <StatCard
                label="Recorded Machine Failures"
                value={formatNumber(summary.failure_count)}
                hint="Ground-truth failure labels"
                icon={AlertTriangle}
                tone="danger"
              />
              <StatCard
                label="Dataset Failure Rate"
                value={formatPercent(summary.failure_rate)}
                hint="Failure count divided by total records"
                icon={Percent}
                tone="warning"
              />
            </div>
          ) : null}
        </section>

        <section aria-labelledby="sensor-monitoring-heading" className="space-y-4">
          <div>
            <h2
              id="sensor-monitoring-heading"
              className="text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase"
            >
              Machine Sensor Monitoring
            </h2>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-500">
              The AI4I 2020 observations are independent synthetic records in
              file order. They do not represent consecutive measurements of the
              same physical machine and are shown here as dataset sample
              comparisons, not real-time telemetry.
            </p>
          </div>

          {initialLoading ? (
            <ChartSkeleton />
          ) : chartError ? (
            <div className="rounded-lg border border-line bg-surface">
              <ErrorState
                title="Sensor samples unavailable"
                message={chartError}
                onRetry={handleRefresh}
              />
            </div>
          ) : (
            <>
              <ChartCard
                title="Air & Process Temperature"
                description={`First ${formatNumber(
                  Math.min(chartRecords.length, CHART_SAMPLE_COUNT)
                )} dataset records, converted from Kelvin to Celsius.`}
                note="Dataset sample comparison. AI4I records are not guaranteed to be consecutive measurements of the same machine, so this is not a chronological machine history."
              >
                <div className="mb-3 flex flex-wrap gap-3 text-[11px] text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="h-2 w-4 rounded-sm bg-cyan-accent"
                      aria-hidden="true"
                    />
                    Air temperature (°C)
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="h-2 w-4 rounded-sm bg-warning"
                      aria-hidden="true"
                    />
                    Process temperature (°C)
                  </span>
                </div>
                <TemperatureChart
                  records={chartRecords}
                  maxSamples={CHART_SAMPLE_COUNT}
                />
              </ChartCard>

              <SensorMetrics
                records={chartRecords}
                maxSamples={CHART_SAMPLE_COUNT}
              />
            </>
          )}
        </section>

        <section aria-labelledby="failure-analysis-heading">
          <h2
            id="failure-analysis-heading"
            className="sr-only"
          >
            Failure Category Analysis
          </h2>
          {initialLoading ? (
            <ChartSkeleton />
          ) : summary ? (
            <ChartCard
              title="Failure Category Analysis"
              description="Ground-truth failure categories recorded in the AI4I 2020 dataset."
              note="These are recorded dataset labels (TWF, HDF, PWF, OSF, RNF) — not AI predictions. Categories can overlap because a single record may carry more than one failure flag."
            >
              <FailureCategories categories={summary.failure_categories} />
            </ChartCard>
          ) : loadError ? (
            <div className="rounded-lg border border-line bg-surface">
              <ErrorState
                title="Failure categories unavailable"
                message={loadError}
                onRetry={handleRefresh}
              />
            </div>
          ) : (
            <CardSkeleton />
          )}
        </section>

        <section aria-labelledby="record-explorer-heading">
          <h2 id="record-explorer-heading" className="sr-only">
            Sensor Record Explorer
          </h2>
          <TelemetryTable refreshToken={tableRefreshToken} />
        </section>

        <p className="pb-4 text-center text-[11px] text-slate-600">
          Failure labels shown are dataset ground truth. Keep them separate from
          model inputs to avoid data leakage in later phases.
        </p>
      </div>
    </div>
  );
}