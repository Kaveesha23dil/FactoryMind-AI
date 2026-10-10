import type { Severity } from "@/types/anomaly";
import { SEVERITY_LABELS } from "@/lib/severity";

export type AnomalySeverityFilter = "all" | Exclude<Severity, "normal">;
interface SeverityFilterProps {
  id: string;
  value: AnomalySeverityFilter;
  onChange: (value: AnomalySeverityFilter) => void;
}

export default function SeverityFilter({ id, value, onChange }: Readonly<SeverityFilterProps>) {
  const options: AnomalySeverityFilter[] = ["all", "low", "medium", "high", "critical"];
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-xs text-slate-500">Severity</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value as AnomalySeverityFilter)}
        className="rounded-md border border-line bg-surface-raised px-3 py-2 text-xs text-white focus:border-accent focus:ring-1 focus:ring-accent focus:outline-none">
        {options.map((option) => <option key={option} value={option}>
          {option === "all" ? "All severities" : SEVERITY_LABELS[option]}
        </option>)}
      </select>
    </div>
  );
}
