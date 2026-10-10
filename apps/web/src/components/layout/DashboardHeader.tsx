import {
  CheckCircle2,
  Database,
  Loader2,
  RefreshCw,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { BackendStatus } from "@/types/monitoring";
import { cn } from "@/lib/format";

interface DashboardHeaderProps {
  title: string;
  subtitle: string;
  datasetLabel: string;
  backendStatus: BackendStatus;
  onRefresh?: () => void;
  refreshing?: boolean;
}

const STATUS_META: Record<
  BackendStatus,
  { label: string; icon: LucideIcon; className: string }
> = {
  checking: {
    label: "Checking backend",
    icon: Loader2,
    className: "border-line bg-surface text-slate-300",
  },
  connected: {
    label: "Backend connected",
    icon: CheckCircle2,
    className: "border-success/30 bg-success/10 text-success",
  },
  unavailable: {
    label: "Backend unavailable",
    icon: XCircle,
    className: "border-danger/30 bg-danger/10 text-danger",
  },
};

export default function DashboardHeader({
  title,
  subtitle,
  datasetLabel,
  backendStatus,
  onRefresh,
  refreshing = false,
}: DashboardHeaderProps) {
  const status = STATUS_META[backendStatus];
  const StatusIcon = status.icon;

  return (
    <header className="flex flex-col gap-4 border-b border-line bg-surface/40 px-4 py-5 sm:px-6 xl:px-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">
            {title}
          </h1>
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <span className="inline-flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-1.5 text-xs text-slate-300">
            <Database className="h-3.5 w-3.5 text-cyan-accent" aria-hidden="true" />
            {datasetLabel}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
              status.className
            )}
          >
            <StatusIcon
              className={cn(
                "h-3.5 w-3.5",
                backendStatus === "checking" && "animate-spin"
              )}
              aria-hidden="true"
            />
            {status.label}
          </span>
          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw
                className={cn(
                  "h-3.5 w-3.5",
                  refreshing && "animate-spin"
                )}
                aria-hidden="true"
              />
              {refreshing ? "Refreshing" : "Refresh"}
            </button>
          )}
        </div>
      </div>
    </header>
  );
}