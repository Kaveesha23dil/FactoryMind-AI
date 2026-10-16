import type { Metadata } from "next";
import MaintenanceReview from "@/components/maintenance/MaintenanceReview";

export const metadata: Metadata = {
  title: "Maintenance Review",
};

export default function MaintenancePage() {
  return (
    <MaintenanceReview />
  );
}
