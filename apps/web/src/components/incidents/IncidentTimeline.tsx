import type { IncidentTimelineEntry } from "@/types/incident";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_TONE,
} from "@/lib/severity";
import { formatDateTime } from "@/lib/format";

interface IncidentTimelineProps {
  entries: IncidentTimelineEntry[];
}

export default function IncidentTimeline({ entries }: IncidentTimelineProps) {
  if (entries.length === 0) {
    return (
      <p className="text-xs text-slate-500">No status history recorded yet.</p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-line pl-5">
      {entries.map((entry, index) => (
        <li key={`${entry.timestamp}-${index}`} className="relative">
          <span
            className="absolute top-1.5 -left-[1.4rem] h-2.5 w-2.5 rounded-full border-2 border-surface bg-cyan-accent"
            aria-hidden="true"
          />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              label={INCIDENT_STATUS_LABELS[entry.status]}
              tone={INCIDENT_STATUS_TONE[entry.status]}
              dot
            />
            <span className="text-[11px] text-slate-500">
              {formatDateTime(entry.timestamp)}
            </span>
          </div>
          {entry.note && (
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              {entry.note}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
