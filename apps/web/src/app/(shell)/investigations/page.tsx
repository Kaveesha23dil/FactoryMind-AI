import type { Metadata } from "next";
import InvestigationBoard from "@/components/investigations/InvestigationBoard";

export const metadata: Metadata = {
  title: "AI Investigations",
};

export default function InvestigationsPage() {
  return <InvestigationBoard />;
}