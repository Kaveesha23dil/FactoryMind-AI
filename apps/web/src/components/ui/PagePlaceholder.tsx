import { Construction } from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";

interface PagePlaceholderProps {
  title: string;
  subtitle: string;
  plannedFor: string;
  description: string;
}

export default function PagePlaceholder({
  title,
  subtitle,
  plannedFor,
  description,
}: PagePlaceholderProps) {
  return (
    <div className="px-4 py-8 sm:px-6 xl:px-8">
      <div className="rounded-lg border border-dashed border-line bg-surface p-8">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md border border-warning/30 bg-warning/10 text-warning">
            <Construction className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h1 className="text-xl font-semibold text-white">{title}</h1>
            <p className="text-sm text-slate-400">{subtitle}</p>
          </div>
          <StatusBadge label="Not implemented yet" tone="danger" dot className="ml-auto" />
        </div>

        <p className="mt-5 max-w-2xl text-sm leading-relaxed text-slate-400">
          {description}
        </p>

        <div className="mt-6 flex items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-warning">Planned:</span>
          <span>{plannedFor}</span>
        </div>
      </div>
    </div>
  );
}