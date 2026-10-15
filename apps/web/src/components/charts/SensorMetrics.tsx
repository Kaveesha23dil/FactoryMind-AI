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
    color: "#6b8e80",
    decimals: 0,
  },
  {
    key: "torque",
    title: "Torque",
    description: "Torque recorded for each dataset record.",
    unit: "Nm",
    color: "#73a88a",
    decimals: 1,
  },
  {
    key: "wear",
    title: "Tool Wear",
    description: "Tool wear accumulated in minutes per dataset record.",
    unit: "min",
    color: "#76b8a8",
    decimals: 0,
  },
];
function MetricLineChart({
  data,
  metric,
}: Readonly<{
  data: Array<{
    sample: number;
    speed: number;
    torque: number;
    wear: number;
  }>;
  metric: MetricDefinition;
}>) {
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
          <CartesianGrid stroke="#dfe9e2" strokeDasharray="3 3" />
          <XAxis
            dataKey="sample"
            tick={{ fontSize: 10, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            tickFormatter={String}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            width={54}
          />
          <Tooltip
            contentStyle={{
              background: "#ffffff",
              border: "1px solid #dfe9e2",
              borderRadius: 8,
              fontSize: 12,
              color: "#264c43",
            }}
            labelStyle={{ color: "#617d6c" }}
            labelFormatter={(label) => `Dataset record #${label}`}
            formatter={(value) => [
              `${formatValue(Number(value))} ${metric.unit}`,
            ]}
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
}: Readonly<SensorMetricsProps>) {
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
