"use client";
import {
  Bar,
  matchByDataKey,
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
import ChartViewport from "@/components/charts/ChartViewport";
import { barAnimation } from "@/components/charts/chartAnimation";
import { useChartData } from "@/components/charts/useChartMotion";
const matchBars = matchByDataKey("severity");
interface SeverityDistributionChartProps {
  distribution: Record<Severity, number>;
}
export default function SeverityDistributionChart({
  distribution,
}: Readonly<SeverityDistributionChartProps>) {
  const data = useChartData(SEVERITY_ORDER.map((severity) => ({
    severity,
    label: SEVERITY_LABELS[severity],
    count: distribution[severity] ?? 0,
  })));
  return (
    <ChartViewport className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
        >
          <CartesianGrid
            stroke="#dfe9e2"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            width={56}
            allowDecimals={false}
            label={{
              value: "Samples",
              angle: -90,
              position: "insideLeft",
              offset: 8,
              fontSize: 11,
              fill: "#718775",
              style: { textAnchor: "middle" },
            }}
          />
          <Tooltip
            wrapperClassName="fm-chart-tooltip"
            animationDuration={140}
            cursor={{ fill: "rgba(148, 163, 184, 0.08)" }}
            contentStyle={{
              background: "#ffffff",
              border: "1px solid #dfe9e2",
              borderRadius: 8,
              fontSize: 12,
              color: "#264c43",
            }}
            labelStyle={{ color: "#617d6c" }}
            formatter={(value) => [
              `${formatNumber(Number(value))} samples`,
              "Count",
            ]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} {...barAnimation(data.length)} animationMatchBy={matchBars}>
            {data.map((entry) => (
              <Cell
                key={entry.severity}
                fill={SEVERITY_COLOR[entry.severity]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartViewport>
  );
}
