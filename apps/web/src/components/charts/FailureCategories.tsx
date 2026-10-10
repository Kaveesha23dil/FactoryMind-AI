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
import type { FailureCategory } from "@/types/monitoring";
import { formatNumber } from "@/lib/format";

interface FailureCategoriesProps {
  categories: FailureCategory[];
}

const BAR_COLORS = ["#2251FF", "#38BDF8", "#F59E0B", "#10B981", "#8B5CF6"];

export default function FailureCategories({
  categories,
}: FailureCategoriesProps) {
  if (categories.length === 0) {
    return (
      <p className="py-12 text-center text-xs text-slate-500">
        No failure categories returned by the backend.
      </p>
    );
  }

  const data = categories.map((category) => ({
    ...category,
    name: `${category.code} - ${category.label}`,
  }));

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 12, bottom: 8, left: 0 }}
        >
          <CartesianGrid stroke="#1E2A43" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="code"
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#94A3B8" }}
            tickLine={{ stroke: "#1E2A43" }}
            axisLine={{ stroke: "#1E2A43" }}
            width={52}
            allowDecimals={false}
            label={{
              value: "Records",
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
            formatter={(value) => [`${formatNumber(Number(value))} records`, "Count"]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((_, index) => (
              <Cell
                key={index}
                fill={BAR_COLORS[index % BAR_COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}