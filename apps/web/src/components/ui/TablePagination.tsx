import { formatNumber } from "@/lib/format";

interface TablePaginationProps {
  page: number;
  pageSize: number;
  total: number;
  noun: string;
  onPageChange: (page: number) => void;
}

export default function TablePagination({ page, pageSize, total, noun, onPageChange }: Readonly<TablePaginationProps>) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total > 0 ? page * pageSize + 1 : 0;
  const end = Math.min((page + 1) * pageSize, total);
  return (
    <div className="flex flex-col gap-3 border-t border-line px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-[11px] text-slate-500">
        Showing {formatNumber(start)}–{formatNumber(end)} of {formatNumber(total)} {noun} · page {page + 1} of {totalPages}
      </p>
      <div className="flex items-center gap-2">
        {[{ label: "Previous", target: page - 1, disabled: page === 0 },
          { label: "Next", target: page + 1, disabled: page >= totalPages - 1 }].map((action) => (
          <button key={action.label} type="button" onClick={() => onPageChange(action.target)} disabled={action.disabled}
            className="rounded-md border border-line bg-surface-raised px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40">
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
