"use client";

import { BrainCircuit, X } from "lucide-react";
import type { FailureCode, TelemetryRecord } from "@/types/monitoring";
import { FAILURE_CATEGORY_LABELS } from "@/lib/failureLabels";
import Modal from "@/components/ui/Modal";
import StatusBadge from "@/components/ui/StatusBadge";
import { cn, formatDecimal, formatNumber } from "@/lib/format";

interface TelemetryDetailsProps {
  record: TelemetryRecord | null;
  onClose: () => void;
}

interface MeasurementRow {
  label: string;
  value: string;
  secondary?: string;
}

export default function TelemetryDetails({
  record,
  onClose,
}: TelemetryDetailsProps) {



  if (!record) return null;

  const measurements: MeasurementRow[] = [
    {
      label: "Air temperature",
      value: `${formatDecimal(record.air_temperature_c, 2)} °C`,
      secondary: `${formatDecimal(record.air_temperature_k, 2)} K`,
    },
    {
      label: "Process temperature",
      value: `${formatDecimal(record.process_temperature_c, 2)} °C`,
      secondary: `${formatDecimal(record.process_temperature_k, 2)} K`,
    },
    {
      label: "Rotational speed",
      value: `${formatNumber(record.rotational_speed_rpm)} rpm`,
    },
    {
      label: "Torque",
      value: `${formatDecimal(record.torque_nm, 1)} Nm`,
    },
    {
      label: "Tool wear",
      value: `${formatNumber(record.tool_wear_min)} min`,
    },
  ];

  return (
    <Modal open={true} onClose={onClose} labelledBy="record-details-title"
      className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-t-lg border border-line bg-surface shadow-2xl outline-none sm:rounded-lg">
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <p className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Dataset record details
            </p>
            <h2
              id="record-details-title"
              className="mt-1 text-lg font-semibold text-white"
            >
              Record #{record.record_id}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {record.machine_failure ? (
              <StatusBadge label="Failure recorded" tone="danger" dot />
            ) : (
              <StatusBadge label="Normal" tone="success" dot />
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close record details"
              className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-surface-raised hover:text-white focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="space-y-5 px-5 py-5">
          <section>
            <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Record metadata
            </h3>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <dt className="text-[11px] text-slate-500">Record ID (UDI)</dt>
                <dd className="mt-0.5 font-medium text-white tabular-nums">
                  {record.record_id}
                </dd>
              </div>
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <dt className="text-[11px] text-slate-500">Product ID</dt>
                <dd className="mt-0.5 font-medium text-white">
                  {record.product_id}
                </dd>
              </div>
              <div className="rounded-md border border-line bg-surface-raised px-3 py-2">
                <dt className="text-[11px] text-slate-500">Machine type</dt>
                <dd className="mt-0.5 font-medium text-white">
                  {record.machine_type}
                </dd>
              </div>
            </dl>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
              The AI4I 2020 dataset provides no timestamp or sensor identity
              columns. This record is a single synthetic observation in file
              order, not a timestamped reading.
            </p>
          </section>

          <section>
            <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Sensor measurements
            </h3>
            <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {measurements.map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface-raised px-3 py-2"
                >
                  <dt className="text-xs text-slate-400">{row.label}</dt>
                  <dd className="text-right">
                    <span className="block text-sm font-medium text-white tabular-nums">
                      {row.value}
                    </span>
                    {row.secondary && (
                      <span className="block text-[11px] text-slate-500 tabular-nums">
                        {row.secondary}
                      </span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </section>

          <section>
            <h3 className="text-[11px] font-medium tracking-[0.12em] text-slate-500 uppercase">
              Recorded failure status
            </h3>
            <div className="mt-3 rounded-md border border-line bg-surface-raised p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-slate-400">Machine failure flag:</span>
                {record.machine_failure ? (
                  <StatusBadge label="Recorded failure" tone="danger" dot />
                ) : (
                  <StatusBadge label="No failure recorded" tone="success" dot />
                )}
              </div>

              <ul className="mt-3 space-y-2">
                {(Object.keys(FAILURE_CATEGORY_LABELS) as FailureCode[]).map(
                  (code) => {
                    const active = record.failure_flags[code] === 1;
                    return (
                      <li
                        key={code}
                        className="flex items-center justify-between gap-3 text-xs"
                      >
                        <span className="text-slate-400">
                          {code} — {FAILURE_CATEGORY_LABELS[code]}
                        </span>
                        <StatusBadge
                          label={active ? "Active" : "Not active"}
                          tone={active ? "danger" : "neutral"}
                        />
                      </li>
                    );
                  }
                )}
              </ul>

              {record.failure_types.length > 0 && (
                <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                  Active categories: {record.failure_types.join(", ")}.
                </p>
              )}
              <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
                These are ground-truth labels from the AI4I 2020 dataset. They
                are recorded outcomes, not AI predictions.
              </p>
            </div>
          </section>

          <section className="rounded-md border border-dashed border-line p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="flex items-center gap-2 text-sm font-medium text-slate-300">
                  <BrainCircuit className="h-4 w-4 text-accent" aria-hidden="true" />
                  Investigate with AI — Coming in Step 4
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  AI-powered, evidence-based root-cause investigation is planned
                  for the next development phase and is not functional yet.
                </p>
              </div>
              <button
                type="button"
                disabled
                aria-disabled="true"
                className={cn(
                  "shrink-0 cursor-not-allowed rounded-md border border-line bg-surface-raised px-3 py-2 text-xs font-medium text-slate-500"
                )}
              >
                Coming in Step 4
              </button>
            </div>
          </section>
        </div>
    </Modal>
  );
}