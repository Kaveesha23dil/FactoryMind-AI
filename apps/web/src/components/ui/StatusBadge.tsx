import { cn } from "@/lib/format";

export type BadgeTone =
  | "neutral"
  | "success"
  | "danger"
  | "accent"
  | "warning";

interface StatusBadgeProps {
  label: string;
  tone: BadgeTone;
  dot?: boolean;
  className?: string;
}

const TONE_STYLES: Record<BadgeTone, string> = {
  neutral: "border-line bg-surface-raised text-slate-300",
  success: "border-success/30 bg-success/10 text-success",
  danger: "border-danger/30 bg-danger/10 text-danger",
  accent: "border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent",
  warning: "border-warning/30 bg-warning/10 text-warning",
};

export default function StatusBadge({
  label,
  tone,
  dot = false,
  className,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium",
        TONE_STYLES[tone],
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            tone === "success" && "bg-success",
            tone === "danger" && "bg-danger",
            tone === "accent" && "bg-cyan-accent",
            tone === "warning" && "bg-warning",
            tone === "neutral" && "bg-slate-400"
          )}
          aria-hidden="true"
        />
      )}
      {label}
    </span>
  );
}