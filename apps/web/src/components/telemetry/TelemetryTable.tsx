"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { getTelemetry } from "@/lib/api";
import type { TelemetryRecord, TelemetryResponse } from "@/types/monitoring";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  EmptyState,
  ErrorState,
  TableSkeleton,
} from "@/components/ui/Feedback";
import TelemetryDetails from "@/components/telemetry/TelemetryDetails";
import { cn, formatDecimal, formatNumber } from "@/lib/format";

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 400;

type StatusFilter = "all" | "failed" | "normal";

interface TelemetryTableProps {
  refreshToken?: number;
}

export default function TelemetryTable({
  refreshToken = 0,
}: TelemetryTableProps) {
  const [page, setPage] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [queryRecordId, setQueryRecordId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [internalRefresh, setInternalRefresh] = useState(0);
  const [data, setData] = useState<TelemetryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<TelemetryRecord | null>(
    null
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      const trimmed = searchInput.trim();
      if (trimmed === "") {
        setQueryRecordId(null);
        return;
      }
      const parsed = Number(trimmed);
      setQueryRecordId(
        Number.isInteger(parsed) && parsed > 0 ? parsed : null
      );
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let stale = false;

    getTelemetry({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      failureOnly: statusFilter === "failed",
      normalOnly: statusFilter === "normal",
      recordId: queryRecordId,
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
            : "Unexpected error while loading records."
        );
        setLoading(false);
      });

    return () => {
      stale = true;
    };
  }, [page, queryRecordId, statusFilter, internalRefresh, refreshToken]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const rangeStart = data && data.total > 0 ? page * PAGE_SIZE + 1 : 0;
  const rangeEnd = data ? Math.min((page + 1) * PAGE_SIZE, data.total) : 0;

  const searchScoped = useMemo(
    () => (queryRecordId !== null ? "Exact ID match" : "Full dataset"),
    [queryRecordId]
  );

  const handleSearchChange = (value: string) => {
    const digitsOnly = value.replace(/[^0-9]/g, "").slice(0, 7);
    if (digitsOnly !== searchInput) {
      setLoading(true);
      setError(null);
    }
    setSearchInput(digitsOnly);
    setPage(0);
  };

  const handleStatusChange = (value: StatusFilter) => {
    setLoading(true);
    setError(null);
    setStatusFilter(value);
    setPage(0);
  };

  const changePage = (next: number) => {
    setLoading(true);
    setError(null);
    setPage(next);
  };

  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex flex-col gap-4 border-b border-line px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">
              Sensor Record Explorer
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              AI4I 2020 records served by the FastAPI backend.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              setError(null);
              setInternalRefresh((value) => value + 1);
            }}
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
          <div className="relative w-full sm:max-w-xs">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-slate-500"
              aria-hidden="true"
            />
            <label htmlFor="record-search" className="sr-only">
              Search records by ID
            </label>
            <input
              id="record-search"
              type="text"
              inputMode="numeric"
              value={searchInput}
              onChange={(event) => handleSearchChange(event.target.value)}
              placeholder="Search by record ID"
              className="w-full rounded-md border border-line bg-surface-raised py-2 pr-3 pl-8 text-xs text-white placeholder:text-slate-500 focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <label
              htmlFor="status-filter"
              className="text-xs text-slate-500"
            >
              Failure status
            </label>
            <select
              id="status-filter"
              value={statusFilter}
              onChange={(event) =>
                handleStatusChange(event.target.value as StatusFilter)
              }
              className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
            >
              <option value="all">All records</option>
              <option value="failed">Failures only</option>
              <option value="normal">Normal only</option>
            </select>
          </div>

          <p className="text-[11px] text-slate-500 sm:ml-auto">
            Filters are applied server-side across the entire dataset
            {searchScoped && ` · search: ${searchScoped}`}
          </p>
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorState
          title="Could not load dataset records"
          message={error}
          onRetry={() => {
            setLoading(true);
            setError(null);
            setInternalRefresh((value) => value + 1);
          }}
        />
      ) : !data || data.records.length === 0 ? (
        <EmptyState
          title="No records found"
          description="No dataset records match the current search and filter settings."
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-left text-xs">
              <caption className="sr-only">
                AI4I 2020 dataset records with sensor measurements and
                recorded failure status
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
                    Air temp (°C)
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Process temp (°C)
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Speed (rpm)
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Torque (Nm)
                  </th>
                  <th scope="col" className="px-3 py-3 font-medium">
                    Tool wear (min)
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Failure status
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.records.map((record) => (
                  <tr
                    key={record.record_id}
                    onClick={() => setSelectedRecord(record)}
                    className="cursor-pointer border-b border-line/60 transition-colors last:border-b-0 hover:bg-surface-raised focus-within:bg-surface-raised"
                  >
                    <td className="px-5 py-3">
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedRecord(record);
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
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      {formatDecimal(record.air_temperature_c, 2)}
                    </td>
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      {formatDecimal(record.process_temperature_c, 2)}
                    </td>
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      {formatNumber(record.rotational_speed_rpm)}
                    </td>
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      {formatDecimal(record.torque_nm, 1)}
                    </td>
                    <td className="px-3 py-3 text-slate-300 tabular-nums">
                      {formatNumber(record.tool_wear_min)}
                    </td>
                    <td className="px-5 py-3">
                      {record.machine_failure ? (
                        <StatusBadge label="Failure" tone="danger" dot />
                      ) : (
                        <StatusBadge label="Normal" tone="success" dot />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-col gap-3 border-t border-line px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[11px] text-slate-500">
              Showing {formatNumber(rangeStart)}–{formatNumber(rangeEnd)} of{" "}
              {formatNumber(data.total)} matching records · page{" "}
              {page + 1} of {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() =>
                  changePage(Math.max(0, page - 1))
                }
                disabled={page === 0}
                className="rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() =>
                  changePage(Math.min(totalPages - 1, page + 1))
                }
                disabled={page >= totalPages - 1}
                className="rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      <TelemetryDetails
        record={selectedRecord}
        onClose={() => setSelectedRecord(null)}
      />
    </section>
  );
}