"use client";
import {
  Bar,
  matchByDataKey,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ScoreBin } from "@/types/anomaly";
import { formatNumber } from "@/lib/format";
import ChartViewport from "@/components/charts/ChartViewport";
import { barAnimation } from "@/components/charts/chartAnimation";
import { useChartData } from "@/components/charts/useChartMotion";
const matchBars = matchByDataKey("range");
interface AnomalyScoreDistributionChartProps {
  histogram: ScoreBin[];
  threshold: number;
}
export default function AnomalyScoreDistributionChart({
  histogram,
  threshold,
}: Readonly<AnomalyScoreDistributionChartProps>) {
  const data = useChartData(histogram.map((bin) => ({
    label: `${bin.bin_start.toFixed(1)}`,
    range: `${bin.bin_start.toFixed(2)} – ${bin.bin_end.toFixed(2)}`,
    count: bin.count,
    anomalous: bin.bin_start >= threshold,
  })));
  const thresholdIndex = histogram.findIndex((bin) => bin.bin_end > threshold);
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
            tick={{ fontSize: 10, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            minTickGap={20}
            label={{
              value: "Anomaly score",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#718775",
            }}
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
            labelFormatter={(_, payload) =>
              payload?.[0]?.payload?.range
                ? `Score ${payload[0].payload.range}`
                : ""
            }
            formatter={(value) => [
              `${formatNumber(Number(value))} samples`,
              "Count",
            ]}
          />
          {thresholdIndex >= 0 && (
            <ReferenceLine
              x={data[thresholdIndex].label}
              stroke="#c9a665"
              strokeDasharray="4 4"
              label={{
                value: `threshold ${threshold.toFixed(1)}`,
                position: "top",
                fontSize: 10,
                fill: "#c9a665",
              }}
            />
          )}
          <Bar dataKey="count" radius={[3, 3, 0, 0]} {...barAnimation(data.length)} animationMatchBy={matchBars}>
            {data.map((entry) => (
              <Cell
                key={entry.range}
                fill={entry.anomalous ? "#cc8f98" : "#6b8e80"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartViewport>
  );
}
