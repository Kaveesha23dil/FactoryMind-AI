"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  CheckCircle2,
  FlaskConical,
  Loader2,
  XCircle,
} from "lucide-react";
import {
  getHealth,
  getInvestigations,
} from "@/lib/api";
import type { BackendStatus } from "@/types/monitoring";
import type {
  InvestigationListPage,
  InvestigationStatus,
} from "@/types/investigation";
import DashboardHeader from "@/components/layout/DashboardHeader";
import StatCard from "@/components/dashboard/StatCard";
import TablePagination from "@/components/ui/TablePagination";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  EmptyState,
  ErrorState,
  KpiGridSkeleton,
  TableSkeleton,
} from "@/components/ui/Feedback";
import {
  INVESTIGATION_STATUS_LABELS,
  INVESTIGATION_STATUS_TONE,
} from "@/lib/investigations";
import { cn, formatDateTime, formatNumber } from "@/lib/format";

const PAGE_SIZE = 20;

type StatusFilter = "all" | InvestigationStatus;

interface InvestigationCounts {
  total: number;
  active: number;
  completed: number;
  failed: number;
}

export default function InvestigationBoard() {
  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("checking");
  const [counts, setCounts] = useState<InvestigationCounts | null>(null);
  const [loadingCounts, setLoadingCounts] = useState(true);
  const [countsError, setCountsError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [page, setPage] = useState(0);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [data, setData] = useState<InvestigationListPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [internalRefresh, setInternalRefresh] = useState(0);

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

    Promise.all([
      getInvestigations({ limit: 1 }),
      getInvestigations({ limit: 1, status: "queued" }),
      getInvestigations({ limit: 1, status: "running" }),
      getInvestigations({ limit: 1, status: "completed" }),
      getInvestigations({ limit: 1, status: "failed" }),
    ])
      .then(([all, queued, running, completed, failed]) => {
        if (stale) return;
        setCounts({
          total: all.total,
          active: queued.total + running.total,
          completed: completed.total,
          failed: failed.total,
        });
        setCountsError(null);
        setLoadingCounts(false);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setCountsError(
          err instanceof Error ? err.message : "Unable to load investigation counts."
        );
        setLoadingCounts(false);
      });

    return () => {
      stale = true;
    };
  }, [internalRefresh]);

  useEffect(() => {
    let stale = false;
    getInvestigations({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      status: status === "all" ? null : status,
    })
      .then((response) => {
        if (stale) return;
        setData(response);
        setError(null);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (stale) return;
        setData(null);
        setError(
          err instanceof Error ? err.message : "Unexpected error while loading investigations."
        );
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [page, status, internalRefresh]);

  const reload = () => {
    setBackendStatus("checking");
    setRefreshing(true);
    setLoadingCounts(true);
    setLoading(true);
    setError(null);
    void getHealth()
      .then((health) =>
        setBackendStatus(
          health.status === "healthy" ? "connected" : "unavailable"
        )
      )
      .catch(() => setBackendStatus("unavailable"))
      .finally(() => setRefreshing(false));
    setInternalRefresh((value) => value + 1);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader
        title="AI Investigations"
        subtitle="Multi-agent root-cause investigations on detected incidents."
        datasetLabel="Gemini 2.5 Flash — FactoryMind agents"
        backendStatus={backendStatus}
        onRefresh={reload}
        refreshing={refreshing}
      />

      <div className="flex-1 space-y-6 px-4 py-6 sm:px-6 xl:px-8">
        <section aria-labelledby="investigation-stats-heading">
          <h2
            id="investigation-stats-heading"
            className="mb-3 text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase"
          >
            Investigation Overview
          </h2>

          {loadingCounts ? (
            <KpiGridSkeleton />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Total investigations"
                value={formatNumber(counts?.total ?? 0)}
                hint="All investigations in the store"
                icon={FlaskConical}
                tone="accent"
              />
              <StatCard
                label="Active"
                value={formatNumber(counts?.active ?? 0)}
                hint="Queued or running"
                icon={Activity}
                tone="warning"
              />
              <StatCard
                label="Completed"
                value={formatNumber(counts?.completed ?? 0)}
                hint="Finished investigations"
                icon={CheckCircle2}
                tone="success"
              />
              <StatCard
                label="Failed"
                value={formatNumber(counts?.failed ?? 0)}
                hint="Investigations with errors"
                icon={XCircle}
                tone="danger"
              />
            </div>
          )}
          {countsError && (
            <p className="mt-2 text-xs text-danger">{countsError}</p>
          )}
        </section>

        <section className="rounded-lg border border-line bg-surface">
          <div className="flex flex-col gap-4 border-b border-line px-5 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">
                  Investigation log
                </h2>
                <p className="mt-1 max-w-2xl text-xs text-slate-400">
                  Root-cause investigations produced by the sensor, knowledge,
                  investigation, and critic agents.
                </p>
              </div>
              <button
                type="button"
                onClick={reload}
                disabled={loading}
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Loader2
                  className={cn("h-3.5 w-3.5", loading && "animate-spin")}
                  aria-hidden="true"
                />
                Refresh
              </button>
            </div>

            <div className="flex items-center gap-2">
              <label
                htmlFor="investigation-status-filter"
                className="text-xs text-slate-500"
              >
                Status
              </label>
              <select
                id="investigation-status-filter"
                value={status}
                onChange={(event) => {
                  setLoading(true);
                  setError(null);
                  setStatus(event.target.value as StatusFilter);
                  setPage(0);
                }}
                className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
              >
                <option value="all">All statuses</option>
                {Object.entries(INVESTIGATION_STATUS_LABELS).map(
                  ([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  )
                )}
              </select>
            </div>
          </div>

          {loading ? (
            <TableSkeleton />
          ) : error ? (
            <ErrorState
              title="Could not load investigations"
              message={error}
              onRetry={reload}
            />
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="No investigations found"
              description="Run an AI investigation from an incident detail page to see it here."
            />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-left text-xs">
                  <caption className="sr-only">
                    Root-cause investigations on detected incidents
                  </caption>
                  <thead>
                    <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                      <th scope="col" className="px-5 py-3 font-medium">
                        Investigation
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium">
                        Incident
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium">
                        Status
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium">
                        Stage
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium">
                        Model
                      </th>
                      <th scope="col" className="px-3 py-3 font-medium">
                        Created
                      </th>
                      <th scope="col" className="px-5 py-3 text-right font-medium">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item) => (
                      <tr
                        key={item.investigation_id}
                        className="border-b border-line/60 transition-colors last:border-b-0 hover:bg-surface-raised"
                      >
                        <td className="px-5 py-3">
                          <Link
                            href={`/investigations/${item.investigation_id}`}
                            className="font-medium text-cyan-accent underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                          >
                            {item.investigation_id}
                          </Link>
                        </td>
                        <td className="px-3 py-3">
                          <Link
                            href={`/incidents/${item.incident_id}`}
                            className="text-slate-300 underline-offset-2 hover:text-slate-200 hover:underline"
                          >
                            {item.incident_id}
                          </Link>
                        </td>
                        <td className="px-3 py-3">
                          <StatusBadge
                            label={INVESTIGATION_STATUS_LABELS[item.status]}
                            tone={INVESTIGATION_STATUS_TONE[item.status]}
                            dot
                          />
                        </td>
                        <td className="px-3 py-3 text-slate-400">
                          {item.stage}
                        </td>
                        <td className="px-3 py-3 font-mono text-[11px] text-slate-400">
                          {item.model}
                        </td>
                        <td className="px-3 py-3 text-slate-400">
                          {formatDateTime(item.created_at)}
                        </td>
                        <td className="px-5 py-3 text-right">
                          <Link
                            href={`/investigations/${item.investigation_id}`}
                            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                          >
                            Open
                            <span aria-hidden="true">
                              {item.status === "running" ||
                              item.status === "queued"
                                ? "…"
                                : "→"}
                            </span>
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <TablePagination
                page={page}
                pageSize={PAGE_SIZE}
                total={data.total}
                noun="investigations"
                onPageChange={(nextPage) => {
                  setLoading(true);
                  setError(null);
                  setPage(nextPage);
                }}
              />
            </>
          )}
        </section>

        <p className="pb-4 text-center text-[11px] text-slate-600">
          AI investigations produce hypotheses and recommended actions for
          review. They never assert a confirmed equipment fault and never use
          ground-truth failure labels.
        </p>
      </div>
    </div>
  );
}