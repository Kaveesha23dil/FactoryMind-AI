"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { ApiError, updateIncidentStatus } from "@/lib/api";
import type { Incident } from "@/types/incident";
import type { IncidentStatus } from "@/types/anomaly";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  INCIDENT_ALLOWED_TRANSITIONS,
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
} from "@/lib/severity";
import { cn } from "@/lib/format";

interface IncidentStatusControlProps {
  incident: Incident;
  onUpdated: (incident: Incident) => void;
}

export default function IncidentStatusControl({
  incident,
  onUpdated,
}: IncidentStatusControlProps) {
  const allowed = INCIDENT_ALLOWED_TRANSITIONS[incident.status];
  const [nextStatus, setNextStatus] = useState<IncidentStatus>(
    allowed[0] ?? incident.status
  );
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await updateIncidentStatus(
        incident.incident_id,
        nextStatus,
        note.trim() === "" ? undefined : note.trim()
      );
      onUpdated(updated);
      setNextStatus(
        INCIDENT_ALLOWED_TRANSITIONS[updated.status][0] ?? updated.status
      );
      setNote("");
      setSuccess(
        `Status updated to ${INCIDENT_STATUS_LABELS[updated.status]}.`
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Could not update the incident status."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-md border border-line bg-surface-raised p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-slate-300">Status workflow</p>
        <StatusBadge
          label={INCIDENT_STATUS_LABELS[incident.status]}
          tone={INCIDENT_STATUS_TONE[incident.status]}
          dot
        />
      </div>

      <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
        Allowed next states:{" "}
        {allowed.map((status) => INCIDENT_STATUS_LABELS[status]).join(", ")}.
      </p>

      <div className="mt-3 space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="flex-1">
            <label
              htmlFor="next-status"
              className="mb-1 block text-[11px] text-slate-500"
            >
              New status
            </label>
            <select
              id="next-status"
              value={nextStatus}
              onChange={(event) => {
                setSuccess(null);
                setNextStatus(event.target.value as IncidentStatus);
              }}
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
            >
              {allowed.map((status) => (
                <option key={status} value={status}>
                  {INCIDENT_STATUS_LABELS[status]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-[2]">
            <label
              htmlFor="status-note"
              className="mb-1 block text-[11px] text-slate-500"
            >
              Note (optional)
            </label>
            <input
              id="status-note"
              type="text"
              value={note}
              maxLength={500}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Add context for this transition"
              className="w-full rounded-md border border-line bg-surface px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md border border-accent/40 bg-accent/15 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-accent/25 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
            submitting && "cursor-not-allowed opacity-60"
          )}
        >
          {submitting && (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          )}
          Update status
        </button>

        {error && <p className="text-xs text-danger">{error}</p>}
        {success && <p className="text-xs text-success">{success}</p>}
      </div>
    </div>
  );
}
