"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, RefreshCw } from "lucide-react";
import { getIncidents } from "@/lib/api";
import type { IncidentListResponse } from "@/types/incident";
import type { IncidentStatus, Severity } from "@/types/anomaly";
import TablePagination from "@/components/ui/TablePagination";
import SeverityFilterControl from "@/components/ui/SeverityFilter";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  EmptyState,
  ErrorState,
  TableSkeleton,
} from "@/components/ui/Feedback";
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  SEVERITY_LABELS,
  SEVERITY_TONE,
} from "@/lib/severity";
import { cn, formatDateTime, formatDecimal } from "@/lib/format";

const PAGE_SIZE = 20;

type StatusFilter = "all" | IncidentStatus;
type SeverityFilter = "all" | Exclude<Severity, "normal">;

interface IncidentTableProps {
  refreshToken?: number;
}

export default function IncidentTable({ refreshToken = 0 }: IncidentTableProps) {
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState<StatusFilter>("all");
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [internalRefresh, setInternalRefresh] = useState(0);
  const [data, setData] = useState<IncidentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stale = false;
    getIncidents({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      status: status === "all" ? null : status,
      severity: severity === "all" ? null : severity,
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
          err instanceof Error
            ? err.message
            : "Unexpected error while loading incidents."
        );
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [page, status, severity, internalRefresh, refreshToken]);

  const reload = () => {
    setLoading(true);
    setError(null);
    setInternalRefresh((value) => value + 1);
  };


  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-col gap-4 border-b border-line px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Incident queue</h2>
            <p className="mt-1 max-w-2xl text-xs text-slate-400">
              Incidents created from detected anomalies. Each incident tracks a
              response status and a full transition history.
            </p>
          </div>
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", loading && "animate-spin")}
              aria-hidden="true"
            />
            Refresh
          </button>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <label htmlFor="incident-status-filter" className="text-xs text-slate-500">
              Status
            </label>
            <select
              id="incident-status-filter"
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
              <option value="open">Open</option>
              <option value="under_review">Under Review</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>

          <SeverityFilterControl id="incidents-severity-filter" value={severity}
            onChange={(value) => {
              setLoading(true);
              setError(null);
              setSeverity(value);
              setPage(0);
            }} />
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState
          title="Could not load incidents"
          message={error}
          onRetry={reload}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No incidents found"
          description="No incidents match the current filter settings. Create incidents from the Anomaly Monitoring page or run a scan."
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-xs">
              <caption className="sr-only">
                Incidents created from detected anomalies
              </caption>
              <thead>
                <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                  <th scope="col" className="px-5 py-3 font-medium">
                    Incident ID
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Record
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Machine type
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Severity
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Anomaly score
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Status
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
                {data.items.map((incident) => (
                  <tr
                    key={incident.incident_id}
                    className="border-b border-line/60 transition-colors last:border-b-0 hover:bg-surface-raised"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/incidents/${incident.incident_id}`}
                        className="font-medium text-cyan-accent underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        {incident.incident_id}
                      </Link>
                    </td>
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      #{incident.record_id}
                    </td>
                    <td className="px-3 py-3">
                      <span className="inline-flex min-w-8 justify-center rounded border border-line bg-surface-raised px-2 py-0.5 font-medium text-slate-300">
                        {incident.machine_type}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={SEVERITY_LABELS[incident.severity]}
                        tone={SEVERITY_TONE[incident.severity]}
                        dot
                      />
                    </td>
                    <td className="px-3 py-3 font-medium text-slate-200 tabular-nums">
                      {formatDecimal(incident.anomaly_score, 2)}
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={INCIDENT_STATUS_LABELS[incident.status]}
                        tone={INCIDENT_STATUS_TONE[incident.status]}
                        dot
                      />
                    </td>
                    <td className="px-3 py-3 text-slate-400">
                      {formatDateTime(incident.created_at)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <Link
                        href={`/incidents/${incident.incident_id}`}
                        className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        Open
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <TablePagination page={page} pageSize={PAGE_SIZE} total={data.total} noun="incidents"
            onPageChange={(nextPage) => {
              setLoading(true);
              setError(null);
              setPage(nextPage);
            }} />
        </>
      )}
    </section>
  );
}
