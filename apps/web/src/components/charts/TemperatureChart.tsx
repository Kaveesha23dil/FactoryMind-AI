"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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
}: TemperatureChartProps) {
  const data = records.slice(0, maxSamples).map((record, index) => ({
    sample: index + 1,
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
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 8, left: 4 }}
        >
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" />
          <XAxis
            dataKey="sample"
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            label={{
              value: "Dataset record (file row)",
              position: "insideBottom",
              offset: -2,
              fontSize: 11,
              fill: "#64748B",
            }}
            tickFormatter={(value) => formatDecimal(Number(value), 0)}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            width={52}
            label={{
              value: "Temperature (°C)",
              angle: -90,
              position: "insideLeft",
              offset: 8,
              fontSize: 11,
              fill: "#64748B",
              style: { textAnchor: "middle" },
            }}
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
            formatter={(value) => [`${formatDecimal(Number(value), 1)} °C`]}
          />
          <Legend
            verticalAlign="top"
            height={28}
            wrapperStyle={{ fontSize: 12 }}
          />
          <Line
            name="Air temperature"
            dataKey="air"
            type="monotone"
            stroke="#38BDF8"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3 }}
            isAnimationActive={false}
          />
          <Line
            name="Process temperature"
            dataKey="process"
            type="monotone"
            stroke="#F59E0B"
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