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
import type { FeatureContribution } from "@/types/anomaly";

interface FeatureContributionChartProps {
  features: FeatureContribution[];
  featureZThreshold: number;
}

export default function FeatureContributionChart({
  features,
  featureZThreshold,
}: FeatureContributionChartProps) {
  const data = features.map((feature) => ({
    name: feature.label,
    zscore: feature.robust_zscore,
    isAnomalous: feature.is_anomalous,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
        >
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            label={{
              value: "Robust z-score (unitless)",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#64748B",
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            width={150}
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
            formatter={(value) => [Number(value).toFixed(2), "z-score"]}
          />
          <ReferenceLine x={featureZThreshold} stroke="#F59E0B" strokeDasharray="4 4" />
          <ReferenceLine x={-featureZThreshold} stroke="#F59E0B" strokeDasharray="4 4" />
          <ReferenceLine x={0} stroke="#334155" />
          <Bar dataKey="zscore" radius={[0, 3, 3, 0]} isAnimationActive={false}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.isAnomalous ? "#EF4444" : "#38BDF8"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
