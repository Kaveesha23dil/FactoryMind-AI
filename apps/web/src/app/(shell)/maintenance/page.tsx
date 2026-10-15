import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Maintenance",
};

export default function MaintenancePage() {
  return (
    <main className="space-y-4 p-6 lg:p-8">
      <h1 className="text-2xl font-semibold text-white">Maintenance review drafts</h1>
      <p className="max-w-2xl text-sm text-slate-300">Open an investigation report to download its technician inspection draft. The draft preserves the recommendation, hypothesis references, evidence IDs and critic concerns, with review and approval left blank.</p>
      <p className="text-sm text-slate-400">Ticket creation, status history and approval audit logs are not implemented. No equipment commands or maintenance actions are executed. A qualified technician must review recommendations under approved site procedures.</p>
      <Link className="inline-block text-cyan-accent underline" href="/investigations">Review investigation recommendations →</Link>
    </main>
  );
}
