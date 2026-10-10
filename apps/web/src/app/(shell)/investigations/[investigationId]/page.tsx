import type { Metadata } from "next";
import InvestigationWorkspace from "@/components/investigations/InvestigationWorkspace";

export const instant = false;

export const metadata: Metadata = {
  title: "Investigation Detail",
  description:
    "Multi-agent AI investigation workspace: agent activity, evidence catalog, hypotheses, critic review, and recommended actions.",
};

export default async function InvestigationDetailPage(
  props: PageProps<"/investigations/[investigationId]">
) {
  const { investigationId } = await props.params;
  return <InvestigationWorkspace investigationId={investigationId} />;
}