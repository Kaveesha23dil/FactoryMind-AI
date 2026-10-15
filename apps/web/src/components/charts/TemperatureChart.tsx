"use client";
import {
  CartesianGrid,
  Legend,
  Scatter,
  ScatterChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TelemetryRecord } from "@/types/monitoring";
import { formatDecimal } from "@/lib/format";
interface TemperatureChartProps {
  records: TelemetryRecord[];
  maxSamples?: number;
}
export default function TemperatureChart({
  records,
  maxSamples = 300,
}: Readonly<TemperatureChartProps>) {
  const data = records.slice(0, maxSamples).map((record) => ({
    sample: record.record_id,
    air: record.air_temperature_c,
    process: record.process_temperature_c,
  }));
  if (data.length === 0) {
    return (
      <p className="py-12 text-center text-xs text-slate-500">
        No temperature samples available.
      </p>
    );
  }
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
          <CartesianGrid stroke="#dfe9e2" strokeDasharray="3 3" />
          <XAxis
            dataKey="sample"
            type="number"
            name="Dataset record"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            label={{
              value: "Dataset observation ID (not time)",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#718775",
            }}
            tickFormatter={(value) => formatDecimal(Number(value), 0)}
          />
          <YAxis
            dataKey="temperature"
            type="number"
            name="Temperature"
            unit="°C"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            width={52}
            label={{
              value: "Temperature (°C)",
              angle: -90,
              position: "insideLeft",
              offset: 8,
              fontSize: 11,
              fill: "#718775",
              style: { textAnchor: "middle" },
            }}
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
            formatter={(value) => [`${formatDecimal(Number(value), 1)} °C`]}
          />
          <Legend
            verticalAlign="top"
            height={28}
            wrapperStyle={{ fontSize: 12 }}
          />
          <Scatter
            name="Air temperature"
            data={data.map((sample) => ({
              sample: sample.sample,
              temperature: sample.air,
            }))}
            fill="#76b8a8"
            isAnimationActive={false}
          />
          <Scatter
            name="Process temperature"
            data={data.map((sample) => ({
              sample: sample.sample,
              temperature: sample.process,
            }))}
            fill="#c9a665"
            isAnimationActive={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
