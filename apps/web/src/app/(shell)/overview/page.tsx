import type { Metadata } from "next";
import Overview from "@/components/dashboard/Overview";

export const metadata: Metadata = {
  title: "Overview",
  description:
    "FactoryMind AI platform overview with AI4I 2020 dataset health and roadmap.",
};

export default function OverviewPage() {
  return <Overview />;
}