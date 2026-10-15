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
import type { FeatureContribution } from "@/types/anomaly";
import ChartViewport from "@/components/charts/ChartViewport";
import { barAnimation } from "@/components/charts/chartAnimation";
import { useChartData } from "@/components/charts/useChartMotion";
const matchBars = matchByDataKey("feature");
interface FeatureContributionChartProps {
  features: FeatureContribution[];
  featureZThreshold: number;
}
export default function FeatureContributionChart({
  features,
  featureZThreshold,
}: Readonly<FeatureContributionChartProps>) {
  const data = useChartData(features.map((feature) => ({
    feature: feature.feature,
    name: feature.label,
    zscore: feature.robust_zscore,
    isAnomalous: feature.is_anomalous,
  })));
  return (
    <ChartViewport className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
        >
          <CartesianGrid
            stroke="#dfe9e2"
            strokeDasharray="3 3"
            horizontal={false}
          />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            label={{
              value: "Robust z-score (unitless)",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#718775",
            }}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            width={150}
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
            formatter={(value) => [Number(value).toFixed(2), "z-score"]}
          />
          <ReferenceLine
            x={featureZThreshold}
            stroke="#c9a665"
            strokeDasharray="4 4"
          />
          <ReferenceLine
            x={-featureZThreshold}
            stroke="#c9a665"
            strokeDasharray="4 4"
          />
          <ReferenceLine x={0} stroke="#9db2a3" />
          <Bar dataKey="zscore" radius={[0, 3, 3, 0]} {...barAnimation(data.length)} animationMatchBy={matchBars}>
            {data.map((entry) => (
              <Cell
                key={entry.feature}
                fill={entry.isAnomalous ? "#cc8f98" : "#76b8a8"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartViewport>
  );
}
