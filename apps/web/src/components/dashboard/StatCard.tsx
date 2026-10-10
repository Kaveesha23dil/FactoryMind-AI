import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/format";

export type StatCardTone = "accent" | "cyan" | "success" | "warning" | "danger";

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  tone: StatCardTone;
  loading?: boolean;
}

const TONE_STYLES: Record<StatCardTone, string> = {
  accent: "border-accent/30 bg-accent/10 text-accent",
  cyan: "border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
};

export default function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
  loading = false,
}: StatCardProps) {
  return (
    <article className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium tracking-[0.12em] text-slate-400 uppercase">
            {label}
          </p>
          <p className="mt-3 truncate text-2xl font-semibold text-white tabular-nums sm:text-3xl">
            {loading ? "—" : value}
          </p>
          {hint && (
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              {loading ? "" : hint}
            </p>
          )}
        </div>
        <span
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-md border",
            TONE_STYLES[tone]
          )}
          aria-hidden="true"
        >
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </article>
  );
}