import type { Metadata } from "next";
import IncidentManagement from "@/components/incidents/IncidentManagement";

export const metadata: Metadata = {
  title: "Incidents",
  description:
    "Incident queue created from detected anomalies, with severity, status workflows, and transition history.",
};

export default function IncidentsPage() {
  return <IncidentManagement />;
}
