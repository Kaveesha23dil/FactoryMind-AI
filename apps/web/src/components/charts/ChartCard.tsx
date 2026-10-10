import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { cn } from "@/lib/format";

interface ChartCardProps {
  title: string;
  description?: string;
  note?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export default function ChartCard({
  title,
  description,
  note,
  actions,
  children,
  className,
}: ChartCardProps) {
  return (
    <section
      className={cn(
        "flex flex-col rounded-lg border border-line bg-surface p-5",
        className
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">{title}</h2>
          {description && (
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              {description}
            </p>
          )}
        </div>
        {actions}
      </div>

      <div className="mt-4 flex-1">{children}</div>

      {note && (
        <p className="mt-4 flex items-start gap-2 border-t border-line pt-3 text-[11px] leading-relaxed text-slate-500">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{note}</span>
        </p>
      )}
    </section>
  );
}