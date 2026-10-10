"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TelemetryRecord } from "@/types/monitoring";
import { formatDecimal, formatNumber } from "@/lib/format";
import ChartCard from "@/components/charts/ChartCard";

interface SensorMetricsProps {
  records: TelemetryRecord[];
  maxSamples?: number;
}

interface MetricDefinition {
  key: "speed" | "torque" | "wear";
  title: string;
  description: string;
  unit: string;
  color: string;
  decimals: number;
}

const METRICS: MetricDefinition[] = [
  {
    key: "speed",
    title: "Rotational Speed",
    description: "Rotational speed recorded for each dataset record.",
    unit: "rpm",
    color: "#2251FF",
    decimals: 0,
  },
  {
    key: "torque",
    title: "Torque",
    description: "Torque recorded for each dataset record.",
    unit: "Nm",
    color: "#10B981",
    decimals: 1,
  },
  {
    key: "wear",
    title: "Tool Wear",
    description: "Tool wear accumulated in minutes per dataset record.",
    unit: "min",
    color: "#38BDF8",
    decimals: 0,
  },
];

function MetricLineChart({
  data,
  metric,
}: {
  data: Array<{ sample: number; speed: number; torque: number; wear: number }>;
  metric: MetricDefinition;
}) {
  const decimals = metric.decimals;
  const formatValue = (value: number) =>
    decimals > 0
      ? formatDecimal(value, decimals)
      : formatNumber(Math.round(value));

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
        >
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" />
          <XAxis
            dataKey="sample"
            tick={{ fontSize: 10, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            tickFormatter={(value) => String(value)}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            width={54}
          />
          <Tooltip
            contentStyle={{
              background: "#16213A",
              border: "1px solid #1E2A43",
              borderRadius: 8,
              fontSize: 12,
              color: "#E2E8F0",
            }}
            labelStyle={{ color: "#94A3B8" }}
            labelFormatter={(label) => `Dataset record #${label}`}
            formatter={(value) => [`${formatValue(Number(value))} ${metric.unit}`]}
          />
          <Line
            name={metric.title}
            dataKey={metric.key}
            type="monotone"
            stroke={metric.color}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function SensorMetrics({
  records,
  maxSamples = 300,
}: SensorMetricsProps) {
  const data = records.slice(0, maxSamples).map((record, index) => ({
    sample: index + 1,
    speed: record.rotational_speed_rpm,
    torque: record.torque_nm,
    wear: record.tool_wear_min,
  }));

  if (data.length === 0) {
    return (
      <p className="py-12 text-center text-xs text-slate-500">
        No sensor samples available.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      {METRICS.map((metric) => (
        <ChartCard
          key={metric.key}
          title={metric.title}
          description={`${metric.description} Unit: ${metric.unit}.`}
        >
          <MetricLineChart data={data} metric={metric} />
        </ChartCard>
      ))}
    </div>
  );
}