import type { Metadata } from "next";
import PagePlaceholder from "@/components/ui/PagePlaceholder";

export const metadata: Metadata = {
  title: "Maintenance",
};

export default function MaintenancePage() {
  return (
    <PagePlaceholder
      title="Maintenance"
      subtitle="Maintenance planning and work order scheduling."
      plannedFor="A later phase — maintenance planning derived from detected incidents."
      description="This page is a placeholder. Maintenance planning is not implemented yet and depends on incident detection from Step 3."
    />
  );
}