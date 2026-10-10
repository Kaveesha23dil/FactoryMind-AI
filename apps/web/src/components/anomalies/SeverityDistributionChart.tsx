"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Severity } from "@/types/anomaly";
import {
  SEVERITY_COLOR,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
} from "@/lib/severity";
import { formatNumber } from "@/lib/format";

interface SeverityDistributionChartProps {
  distribution: Record<Severity, number>;
}

export default function SeverityDistributionChart({
  distribution,
}: SeverityDistributionChartProps) {
  const data = SEVERITY_ORDER.map((severity) => ({
    severity,
    label: SEVERITY_LABELS[severity],
    count: distribution[severity] ?? 0,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            width={56}
            allowDecimals={false}
            label={{
              value: "Samples",
              angle: -90,
              position: "insideLeft",
              offset: 8,
              fontSize: 11,
              fill: "#64748B",
              style: { textAnchor: "middle" },
            }}
          />
          <Tooltip
            cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
            contentStyle={{
              background: "#16213A",
              border: "1px solid #1E2A43",
              borderRadius: 8,
              fontSize: 12,
              color: "#E2E8F0",
            }}
            labelStyle={{ color: "#94A3B8" }}
            formatter={(value) => [
              `${formatNumber(Number(value))} samples`,
              "Count",
            ]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.severity} fill={SEVERITY_COLOR[entry.severity]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
