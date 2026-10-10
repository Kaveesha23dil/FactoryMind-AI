"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { getAnomalies } from "@/lib/api";
import type { AnomalyListResponse, Severity } from "@/types/anomaly";
import TablePagination from "@/components/ui/TablePagination";
import SeverityFilterControl from "@/components/ui/SeverityFilter";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  EmptyState,
  ErrorState,
  TableSkeleton,
} from "@/components/ui/Feedback";
import AnomalyDetails from "@/components/anomalies/AnomalyDetails";
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
  SEVERITY_LABELS,
  SEVERITY_TONE,
  featureLabel,
} from "@/lib/severity";
import { cn, formatDecimal } from "@/lib/format";

const PAGE_SIZE = 20;

type SeverityFilter = "all" | Exclude<Severity, "normal">;
type MachineFilter = "all" | "L" | "M" | "H";

interface AnomalyTableProps {
  refreshToken?: number;
}

export default function AnomalyTable({ refreshToken = 0 }: AnomalyTableProps) {
  const [page, setPage] = useState(0);
  const [severity, setSeverity] = useState<SeverityFilter>("all");
  const [machineType, setMachineType] = useState<MachineFilter>("all");
  const [internalRefresh, setInternalRefresh] = useState(0);
  const [data, setData] = useState<AnomalyListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRecordId, setSelectedRecordId] = useState<number | null>(null);

  useEffect(() => {
    let stale = false;
    getAnomalies({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      severity: severity === "all" ? null : severity,
      machineType: machineType === "all" ? null : machineType,
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
            : "Unexpected error while loading anomalies."
        );
        setLoading(false);
      });
    return () => {
      stale = true;
    };
  }, [page, severity, machineType, internalRefresh, refreshToken]);

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
            <h2 className="text-sm font-semibold text-white">
              Anomaly records
            </h2>
            <p className="mt-1 max-w-2xl text-xs text-slate-400">
              Detected anomalies ranked by anomaly score. Severity is an
              application-defined anomaly level; it is not a calibrated failure
              probability and is separate from the dataset&apos;s ground-truth
              failure label.
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
          <SeverityFilterControl id="anomalies-severity-filter" value={severity}
            onChange={(value) => {
              setLoading(true);
              setError(null);
              setSeverity(value);
              setPage(0);
            }} />

          <div className="flex items-center gap-2">
            <label htmlFor="machine-filter" className="text-xs text-slate-500">
              Machine type
            </label>
            <select
              id="machine-filter"
              value={machineType}
              onChange={(event) => {
                setLoading(true);
                setError(null);
                setMachineType(event.target.value as MachineFilter);
                setPage(0);
              }}
              className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
            >
              <option value="all">All types</option>
              <option value="L">L</option>
              <option value="M">M</option>
              <option value="H">H</option>
            </select>
          </div>

          <p className="text-[11px] text-slate-500 sm:ml-auto">
            Filters are applied server-side across the entire dataset
          </p>
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState
          title="Could not load anomalies"
          message={error}
          onRetry={reload}
        />
      ) : !data || data.records.length === 0 ? (
        <EmptyState
          title="No anomalies found"
          description="No detected anomalies match the current filter settings."
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left text-xs">
              <caption className="sr-only">
                Detected anomalous dataset observations with severity and
                incident status
              </caption>
              <thead>
                <tr className="border-b border-line text-[11px] tracking-[0.1em] text-slate-500 uppercase">
                  <th scope="col" className="px-5 py-3 font-medium">
                    Record ID
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Machine type
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Anomaly score
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Severity
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Main anomalous feature
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Incident status
                  </th>
                  <th scope="col" className="px-5 py-3 text-right font-medium">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.records.map((record) => (
                  <tr
                    key={record.record_id}
                    className="border-b border-line/60 transition-colors last:border-b-0 hover:bg-surface-raised"
                  >
                    <td className="px-5 py-3">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedRecordId(record.record_id);
                        }}
                        className="font-medium text-cyan-accent underline-offset-2 hover:underline focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        #{record.record_id}
                      </button>
                    </td>
                    <td className="px-3 py-3">
                      <span className="inline-flex min-w-8 justify-center rounded border border-line bg-surface-raised px-2 py-0.5 font-medium text-slate-300">
                        {record.machine_type}
                      </span>
                    </td>
                    <td className="px-3 py-3 font-medium text-slate-200 tabular-nums">
                      {formatDecimal(record.anomaly_score, 2)}
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge
                        label={SEVERITY_LABELS[record.severity]}
                        tone={SEVERITY_TONE[record.severity]}
                        dot
                      />
                    </td>
                    <td className="px-3 py-3 text-slate-300">
                      {record.main_anomalous_feature
                        ? featureLabel(record.main_anomalous_feature)
                        : "—"}
                      {record.anomalous_feature_count > 1 && (
                        <span className="ml-1 text-[11px] text-slate-500">
                          +{record.anomalous_feature_count - 1} more
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {record.incident_status ? (
                        <StatusBadge
                          label={
                            INCIDENT_STATUS_LABELS[record.incident_status]
                          }
                          tone={INCIDENT_STATUS_TONE[record.incident_status]}
                          dot
                        />
                      ) : (
                        <span className="text-slate-500">No incident</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedRecordId(record.record_id);
                        }}
                        className="rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <TablePagination page={page} pageSize={PAGE_SIZE} total={data.total} noun="anomalies"
            onPageChange={(nextPage) => {
              setLoading(true);
              setError(null);
              setPage(nextPage);
            }} />
        </>
      )}

      <AnomalyDetails
        key={selectedRecordId ?? "closed"}
        recordId={selectedRecordId}
        onClose={() => setSelectedRecordId(null)}
        onIncidentChange={reload}
      />
    </section>
  );
}
