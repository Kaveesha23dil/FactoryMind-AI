import type { FailureCode } from "@/types/monitoring";

export const FAILURE_CATEGORY_LABELS: Record<FailureCode, string> = {
  TWF: "Tool Wear Failure",
  HDF: "Heat Dissipation Failure",
  PWF: "Power Failure",
  OSF: "Overstrain Failure",
  RNF: "Random Failure",
};

export const FAILURE_CODES = Object.keys(
  FAILURE_CATEGORY_LABELS
) as FailureCode[];