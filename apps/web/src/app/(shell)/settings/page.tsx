import type { Metadata } from "next";
import PagePlaceholder from "@/components/ui/PagePlaceholder";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <PagePlaceholder
      title="Settings"
      subtitle="Workspace and platform configuration."
      plannedFor="A later phase — API endpoints, thresholds, and workspace preferences."
      description="This page is a placeholder. Authentication, workspace configuration, and platform settings are intentionally out of scope for Step 2."
    />
  );
}