import { AlertTriangle, Loader2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/format";

function SkeletonRow({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-surface-raised", className)}
      aria-hidden="true"
    />
  );
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-line bg-surface p-5",
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-3">
          <SkeletonRow className="h-3 w-24" />
          <SkeletonRow className="h-7 w-32" />
          <SkeletonRow className="h-3 w-40" />
        </div>
        <SkeletonRow className="h-10 w-10 rounded-md" />
      </div>
    </div>
  );
}

export function KpiGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <CardSkeleton key={index} />
      ))}
    </div>
  );
}

export function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-line bg-surface p-5",
        className
      )}
    >
      <div className="flex flex-col gap-1.5">
        <SkeletonRow className="h-4 w-48" />
        <SkeletonRow className="h-3 w-64" />
      </div>
      <SkeletonRow className="mt-6 h-56 w-full" />
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      <div className="space-y-4 border-b border-line p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-2">
            <SkeletonRow className="h-9 w-56" />
            <SkeletonRow className="h-9 w-36" />
          </div>
          <SkeletonRow className="h-9 w-40" />
        </div>
      </div>
      <div className="space-y-0">
        {Array.from({ length: 8 }).map((_, index) => (
          <div
            key={index}
            className="flex items-center gap-4 border-b border-line px-4 py-3 last:border-b-0"
          >
            <SkeletonRow className="h-4 w-16" />
            <SkeletonRow className="h-4 w-10" />
            <SkeletonRow className="h-4 w-20" />
            <SkeletonRow className="h-4 w-20" />
            <SkeletonRow className="h-4 w-16" />
            <SkeletonRow className="h-4 w-14" />
            <SkeletonRow className="h-4 w-14" />
            <SkeletonRow className="ml-auto h-6 w-20" />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between border-t border-line p-3">
        <SkeletonRow className="h-4 w-36" />
        <div className="flex gap-2">
          <SkeletonRow className="h-8 w-24" />
          <SkeletonRow className="h-8 w-24" />
        </div>
      </div>
    </div>
  );
}

interface LoadingOverlayProps {
  label?: string;
}

export function LoadingIndicator({ label = "Loading" }: LoadingOverlayProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400">
      <Loader2 className="h-4 w-4 animate-spin text-cyan-accent" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
}

export function EmptyState({
  title,
  description,
  icon: Icon = AlertTriangle,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-md border border-line bg-surface-raised text-slate-400">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div>
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
    </div>
  );
}

interface ErrorStateProps {
  title: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-md border border-danger/30 bg-danger/10 text-danger">
        <AlertTriangle className="h-5 w-5" aria-hidden="true" />
      </span>
      <div>
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
          {message}
        </p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
        >
          Try again
        </button>
      )}
    </div>
  );
}