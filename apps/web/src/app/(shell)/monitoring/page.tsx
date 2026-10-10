import type { Metadata } from "next";
import Dashboard from "@/components/dashboard/Dashboard";

export const metadata: Metadata = {
  title: "Machine Monitoring",
  description:
    "Real-time view of AI4I 2020 sensor records, failure categories, and the dataset record explorer.",
};

export default function MonitoringPage() {
  return <Dashboard />;
}