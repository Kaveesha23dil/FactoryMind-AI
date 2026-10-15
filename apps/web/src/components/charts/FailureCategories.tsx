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
import type { FailureCategory } from "@/types/monitoring";
import { formatNumber } from "@/lib/format";
import ChartViewport from "@/components/charts/ChartViewport";
import { barAnimation } from "@/components/charts/chartAnimation";
import { useChartData } from "@/components/charts/useChartMotion";
const matchBars = matchByDataKey("code");
interface FailureCategoriesProps {
  categories: FailureCategory[];
}
const BAR_COLORS = ["#6b8e80", "#76b8a8", "#c9a665", "#73a88a", "#a8a5cf"];
export default function FailureCategories({
  categories,
}: Readonly<FailureCategoriesProps>) {
  const data = useChartData(categories.map((category) => ({
    ...category,
    name: `${category.code} - ${category.label}`,
  })));
  if (categories.length === 0) {
    return (
      <p className="py-12 text-center text-xs text-slate-500">
        No failure categories returned by the backend.
      </p>
    );
  }
  return (
    <ChartViewport className="h-72 w-full">
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
            dataKey="code"
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "#617d6c" }}
            tickLine={{ stroke: "#dfe9e2" }}
            axisLine={{ stroke: "#dfe9e2" }}
            width={52}
            allowDecimals={false}
            label={{
              value: "Records",
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
              `${formatNumber(Number(value))} records`,
              "Count",
            ]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]} {...barAnimation(data.length)} animationMatchBy={matchBars}>
            {data.map((entry, index) => (
              <Cell
                key={entry.code}
                fill={BAR_COLORS[index % BAR_COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartViewport>
  );
}
