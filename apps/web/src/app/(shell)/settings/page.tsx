import type { Metadata } from "next";
import SettingsDashboard from "@/components/settings/SettingsDashboard";

export const metadata: Metadata = {
  title: "Settings",
};

export default function SettingsPage() {
  return (
    <SettingsDashboard />
  );
}
