"use client";
import type { InvestigationReport } from "@/types/investigation";

export default function InspectionDraft({ report }: Readonly<{ report: InvestigationReport }>) {
  function download() {
    const text = ["FactoryMind AI — technician review DRAFT", `Investigation: ${report.investigation_id}`, `Incident: ${report.incident_id}`,
      "Synthetic benchmark/reference material. No ticket or equipment action has been executed.",
      "Technician review: __________  Approval: __________  Date: __________", "", report.summary, "", "Recommended checks:",
      ...report.recommended_actions.map((item, index) => `${index + 1}. ${item.action}\nRationale: ${item.rationale}\nHypotheses: ${item.supporting_hypothesis_ids.join(", ")}`),
      "", "Stored evidence IDs:", ...report.evidence_catalog, "", "Critic issues:", ...report.critic_review.issues_found, ...report.critic_review.citation_issues,
      "", "Follow approved site isolation procedures and qualified-person review. This draft is not work authorization."].join("\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${report.investigation_id}-inspection-draft.txt`; anchor.click(); URL.revokeObjectURL(url);
  }
  return <div className="mt-4 border-t border-line pt-4"><button type="button" onClick={download} className="rounded border border-line px-3 py-2 text-xs text-cyan-accent hover:bg-surface-raised">Download technician review draft</button><p className="mt-2 text-xs text-slate-500">Draft only. Human review and approval remain blank; no maintenance ticket or equipment action is created.</p></div>;
}
