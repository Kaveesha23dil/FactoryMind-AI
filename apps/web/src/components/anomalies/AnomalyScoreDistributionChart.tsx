"use client";

import {
  Bar,
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

interface AnomalyScoreDistributionChartProps {
  histogram: ScoreBin[];
  threshold: number;
}

export default function AnomalyScoreDistributionChart({
  histogram,
  threshold,
}: AnomalyScoreDistributionChartProps) {
  const data = histogram.map((bin) => ({
    label: `${bin.bin_start.toFixed(1)}`,
    range: `${bin.bin_start.toFixed(2)} – ${bin.bin_end.toFixed(2)}`,
    count: bin.count,
    anomalous: bin.bin_start >= threshold,
  }));

  const thresholdIndex = histogram.findIndex(
    (bin) => bin.bin_end > threshold
  );

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            minTickGap={20}
            label={{
              value: "Anomaly score",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#64748B",
            }}
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
              stroke="#F59E0B"
              strokeDasharray="4 4"
              label={{
                value: `threshold ${threshold.toFixed(1)}`,
                position: "top",
                fontSize: 10,
                fill: "#F59E0B",
              }}
            />
          )}
          <Bar dataKey="count" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.anomalous ? "#EF4444" : "#2251FF"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
