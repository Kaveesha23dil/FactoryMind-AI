import type { Metadata } from "next";
import PagePlaceholder from "@/components/ui/PagePlaceholder";

export const metadata: Metadata = {
  title: "Incidents",
};

export default function IncidentsPage() {
  return (
    <PagePlaceholder
      title="Incidents"
      subtitle="Anomaly detection and incident management."
      plannedFor="Step 3 — anomaly detection, incident creation, and AI-powered investigation."
      description="This page is a placeholder. Incident detection and management are not implemented yet. The Machine Monitoring dashboard is the only functional monitoring surface at this stage."
    />
  );
}