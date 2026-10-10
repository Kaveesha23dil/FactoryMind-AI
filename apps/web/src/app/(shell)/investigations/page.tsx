import type { Metadata } from "next";
import PagePlaceholder from "@/components/ui/PagePlaceholder";

export const metadata: Metadata = {
  title: "AI Investigations",
};

export default function InvestigationsPage() {
  return (
    <PagePlaceholder
      title="AI Investigations"
      subtitle="Multi-agent, evidence-driven root cause analysis."
      plannedFor="Step 3 — evidence-driven AI investigation using the ground-truth record context."
      description="This page is a placeholder. AI investigation is not functional yet. The 'Investigate with AI' action inside record details is intentionally disabled until Step 3 is implemented."
    />
  );
}