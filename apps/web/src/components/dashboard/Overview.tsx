"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Activity,
  CheckCircle2,
  Database,
  Percent,
} from "lucide-react";
import { getDatasetSummary, getHealth } from "@/lib/api";
import type { BackendStatus, DatasetSummary } from "@/types/monitoring";
import { formatNumber, formatPercent } from "@/lib/format";
import DashboardHeader from "@/components/layout/DashboardHeader";
import StatCard from "@/components/dashboard/StatCard";
import {
  ErrorState,
  KpiGridSkeleton,
} from "@/components/ui/Feedback";

interface RoadmapItem {
  href: string;
  title: string;
  description: string;
  status: "available" | "planned";
}

const ROADMAP: RoadmapItem[] = [
  {
    href: "/monitoring",
    title: "Machine Monitoring",
    description:
      "Sensor comparison charts, failure category analysis, and the dataset record explorer.",
    status: "available",
  },
  {
    href: "/anomalies",
    title: "Anomaly Monitoring",
    description:
      "Unsupervised anomaly detection with severity ranking, feature evidence, and held-out evaluation.",
    status: "available",
  },
  {
    href: "/incidents",
    title: "Incidents",
    description:
      "Incident queue with severity, status workflows, and full transition history.",
    status: "available",
  },
  {
    href: "/investigations",
    title: "AI Investigations",
    description:
      "Multi-agent, evidence-driven root cause investigation workflow.",
    status: "planned",
  },
];

export default function Overview() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const [summary, setSummary] = useState<DatasetSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function fetchOverviewData() {
    return Promise.allSettled([getHealth(), getDatasetSummary()]);
  }

  const applyResults = useCallback(
    (results: Awaited<ReturnType<typeof fetchOverviewData>>) => {
      const [healthResult, summaryResult] = results;

      if (healthResult.status === "fulfilled") {
        setBackendStatus(
          healthResult.value.status === "healthy" ? "connected" : "unavailable"
        );
      } else {
        setBackendStatus("unavailable");
      }

      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
        setError(null);
      } else {
        const reason = summaryResult.reason;
        setError(
          reason instanceof Error ? reason.message : "Unable to load summary."
        );
      }

      setLoading(false);
    },
    []
  );

  useEffect(() => {
    let stale = false;
    void fetchOverviewData().then((results) => {
      if (stale) return;
      applyResults(results);
    });
    return () => {
      stale = true;
    };
  }, [applyResults]);

  const handleRefresh = useCallback(() => {
    setBackendStatus("checking");
    setError(null);
    setRefreshing(true);
    void fetchOverviewData()
      .then((results) => {
        setLoading(false);
        applyResults(results);
      })
      .finally(() => setRefreshing(false));
  }, [applyResults]);

  const machineTypes = summary?.machine_types ?? [];
  const maxTypeCount = machineTypes.reduce(
    (max, item) => Math.max(max, item.count),
    0
  );

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader
        title="Overview"
        subtitle="Platform overview and AI4I 2020 dataset health."
        datasetLabel="AI4I 2020 — Synthetic Dataset"
        backendStatus={backendStatus}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        {loading ? (
          <KpiGridSkeleton />
        ) : error && !summary ? (
          <div className="rounded-lg border border-line bg-surface">
            <ErrorState
              title="Dataset summary unavailable"
              message={error}
              onRetry={handleRefresh}
            />
          </div>
        ) : summary ? (
          <>
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
                hint="No failure recorded"
                icon={CheckCircle2}
                tone="success"
              />
              <StatCard
                label="Recorded Failures"
                value={formatNumber(summary.failure_count)}
                hint="Ground-truth failure labels"
                icon={AlertTriangle}
                tone="danger"
              />
              <StatCard
                label="Failure Rate"
                value={formatPercent(summary.failure_rate)}
                hint="Failures divided by total records"
                icon={Percent}
                tone="warning"
              />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <section className="rounded-lg border border-line bg-surface p-5">
                <h2 className="text-sm font-semibold text-white">
                  Machine Type Distribution
                </h2>
                <p className="mt-1 text-xs text-slate-400">
                  Record counts by AI4I machine quality variant.
                </p>
                <ul className="mt-4 space-y-3">
                  {machineTypes.map((item) => (
                    <li key={item.type}>
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-slate-300">
                          Type {item.type}
                        </span>
                        <span className="text-slate-400 tabular-nums">
                          {formatNumber(item.count)} records
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-raised">
                        <div
                          className="h-full rounded-full bg-cyan-accent"
                          style={{
                            width: `${
                              maxTypeCount > 0
                                ? (item.count / maxTypeCount) * 100
                                : 0
                            }%`,
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="rounded-lg border border-line bg-surface p-5">
                <h2 className="text-sm font-semibold text-white">
                  Dataset Information
                </h2>
                <dl className="mt-4 space-y-3 text-xs">
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Dataset</dt>
                    <dd className="text-right text-slate-300">
                      {summary.dataset}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Source</dt>
                    <dd className="text-right text-slate-300">
                      {summary.source}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Failure categories</dt>
                    <dd className="text-right text-slate-300">
                      {summary.failure_categories
                        .map((category) => category.code)
                        .join(", ")}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-500">Backend API</dt>
                    <dd className="text-right text-slate-300">
                      FastAPI · /api/dataset/summary
                    </dd>
                  </div>
                </dl>
                <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-slate-500">
                  AI4I 2020 is a synthetic benchmark dataset. Records do not
                  include timestamps or physical machine identifiers and are
                  not a chronological machine history.
                </p>
              </section>
            </div>
          </>
        ) : null}

        <section className="rounded-lg border border-line bg-surface p-5">
          <h2 className="text-sm font-semibold text-white">Platform Roadmap</h2>
          <p className="mt-1 text-xs text-slate-400">
            FactoryMind AI is built in phases. Available features are live;
            planned features are not implemented yet.
          </p>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {ROADMAP.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="group flex flex-col gap-2 rounded-lg border border-line bg-surface-raised p-4 transition-colors hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
              >
                <div className="flex items-center justify-between">
                  <span className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface text-cyan-accent">
                    {item.status === "available" ? (
                      <Activity className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                    )}
                  </span>
                  <span
                    className={
                      item.status === "available"
                        ? "rounded border border-success/30 bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success"
                        : "rounded border border-line px-2 py-0.5 text-[10px] font-medium text-slate-500"
                    }
                  >
                    {item.status === "available" ? "Available" : "Planned"}
                  </span>
                </div>
                <p className="text-sm font-medium text-white">{item.title}</p>
                <p className="text-xs leading-relaxed text-slate-400">
                  {item.description}
                </p>
                <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-cyan-accent">
                  {item.status === "available" ? "Open" : "View placeholder"}
                  <ArrowRight
                    className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </span>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}