"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  Factory,
  LayoutDashboard,
  Menu,
  Settings,
  Wrench,
  X,
} from "lucide-react";
import { cn } from "@/lib/format";

interface NavItem {
  href: string;
  label: string;
  icon: typeof Activity;
  comingSoon?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/monitoring", label: "Machine Monitoring", icon: Activity },
  { href: "/incidents", label: "Incidents", icon: AlertTriangle, comingSoon: true },
  { href: "/investigations", label: "AI Investigations", icon: Bot, comingSoon: true },
  { href: "/maintenance", label: "Maintenance", icon: Wrench, comingSoon: true },
  { href: "/settings", label: "Settings", icon: Settings, comingSoon: true },
];

function BrandMark() {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-md border border-accent/40 bg-accent/15 text-accent">
        <Factory className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-wide text-white">
          FactoryMind AI
        </span>
        <span className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
          Industrial Intelligence
        </span>
      </span>
    </div>
  );
}

export default function AppSidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed top-3 left-3 z-40 flex h-10 w-10 items-center justify-center rounded-md border border-line bg-surface text-slate-200 transition-colors hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none lg:hidden"
        aria-label="Open navigation menu"
        aria-expanded={open}
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>

      {open && (
        <button
          type="button"
          tabIndex={-1}
          aria-label="Close navigation menu"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-line bg-surface transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
        aria-label="Primary navigation"
      >
        <div className="flex h-16 items-center justify-between border-b border-line px-5">
          <BrandMark />
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-surface-raised hover:text-white focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none lg:hidden"
            aria-label="Close navigation menu"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-2 text-[11px] font-medium tracking-[0.14em] text-slate-500 uppercase">
            Platform
          </p>
          <ul className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                      active
                        ? "border-accent bg-accent/10 text-white"
                        : "border-transparent text-slate-400 hover:border-line hover:bg-surface-raised hover:text-slate-200"
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        active ? "text-cyan-accent" : "text-slate-500"
                      )}
                      aria-hidden="true"
                    />
                    <span className="flex-1">{item.label}</span>
                    {item.comingSoon && (
                      <span className="rounded border border-line px-1.5 py-0.5 text-[10px] text-slate-500">
                        Soon
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-line px-5 py-4 text-[11px] leading-relaxed text-slate-500">
          AI4I 2020 dataset integration
          <br />
          Step 2 of the FactoryMind AI roadmap
        </div>
      </aside>
    </>
  );
}