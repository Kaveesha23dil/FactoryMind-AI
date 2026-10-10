import type { Metadata } from "next";
import AnomalyMonitoring from "@/components/anomalies/AnomalyMonitoring";

export const metadata: Metadata = {
  title: "Anomaly Monitoring",
  description:
    "Unsupervised anomaly detection over AI4I 2020 sensor records with severity ranking, evaluation, and incident creation.",
};

export default function AnomaliesPage() {
  return <AnomalyMonitoring />;
}
