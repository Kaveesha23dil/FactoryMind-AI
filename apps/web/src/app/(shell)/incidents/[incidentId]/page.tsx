import type { Metadata } from "next";
import IncidentDetail from "@/components/incidents/IncidentDetail";

export const instant = false;

export const metadata: Metadata = {
  title: "Incident Detail",
  description:
    "Evidence-based incident detail view with anomaly contributions, status workflow, and transition history.",
};

export default async function IncidentDetailPage(
  props: PageProps<"/incidents/[incidentId]">
) {
  const { incidentId } = await props.params;
  return <IncidentDetail incidentId={incidentId} />;
}
