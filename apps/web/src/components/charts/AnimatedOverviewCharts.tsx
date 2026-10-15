"use client";
import { useId } from "react";
import type { SubmissionOverview } from "@/types/submission";
import ChartViewport from "./ChartViewport";
import { useAnimatedNumbers } from "./useChartMotion";
import { CHART_MOTION } from "./chartAnimation";

const SEVERITIES = [{ name: "low", color: "#cceba0" }, { name: "medium", color: "#85cfc4" }, { name: "high", color: "#f0b9bb" }, { name: "critical", color: "#a5a9e5" }];
const STATES = ["completed", "failed", "running", "queued"];
const number = (value: number) => value.toLocaleString("en-US");

function Donut({ data }: Readonly<{ data: SubmissionOverview }>) {
  const maskId = useId();
  const counts = SEVERITIES.map(item => data.severity_distribution[item.name] ?? 0);
  const animated = useAnimatedNumbers(counts, CHART_MOTION.pie, false);
  const [sweep] = useAnimatedNumbers([1], CHART_MOTION.pie);
  const total = counts.reduce((sum, count) => sum + count, 0);
  const animatedTotal = animated.reduce((sum, count) => sum + count, 0);
  const description = SEVERITIES.map((item, index) => `${item.name} ${counts[index]}`).join(", ");
  return <div className="fm-donut-area"><div className="fm-donut"><svg viewBox="0 0 200 200" role="img" aria-label={`Anomaly severity: ${description}`}>
    <defs><mask id={maskId}><circle cx="100" cy="100" r="50" fill="none" stroke="white" strokeWidth="100" pathLength="100" strokeDasharray={`${sweep * 100} 100`} transform="rotate(-90 100 100)" /></mask></defs>
    <circle cx="100" cy="100" r="74" fill="none" stroke="#edf3ef" strokeWidth="25" />
    <g mask={`url(#${maskId})`} data-pie-sweep={sweep.toFixed(3)}>{SEVERITIES.map((item, index) => {
      const length = animatedTotal ? animated[index] / animatedTotal * 100 : 0;
      const start = animatedTotal ? animated.slice(0, index).reduce((sum, count) => sum + count, 0) / animatedTotal * 100 : 0;
      return <g className="fm-pie-segment" key={item.name}><title>{item.name}: {counts[index]}</title><circle cx="100" cy="100" r="74" fill="none" stroke={item.color} strokeWidth="25" pathLength="100" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} transform="rotate(-90 100 100)" /></g>;
    })}</g>
  </svg><div className="fm-donut-label"><span>Total anomalies</span><strong>{number(total)}</strong><small>benchmark observations</small></div></div><div className="fm-legend fm-chart-pie-legend">{SEVERITIES.map((item, index) => <div key={item.name}><span style={{ background: item.color }} /><p>{item.name}</p><b>{number(counts[index])}</b></div>)}</div></div>;
}

export function AnimatedSeverityDonut({ data }: Readonly<{ data: SubmissionOverview }>) {
  return <ChartViewport className="fm-donut-viewport"><Donut data={data} /></ChartViewport>;
}

function JobBars({ investigations }: Readonly<{ investigations: Record<string, number> }>) {
  const maximum = Math.max(1, ...STATES.map(key => investigations[key] ?? 0));
  const heights = useAnimatedNumbers(STATES.map(key => (investigations[key] ?? 0) / maximum * 100), CHART_MOTION.bar, true, CHART_MOTION.stagger);
  return <div className="fm-bar-chart">{STATES.map((key, index) => <div className="fm-bar-column" key={key}><span className="fm-bar-value">{investigations[key]}</span><div className="fm-bar-track"><div className={`fm-bar-fill fm-bar-${index}`} style={{ height: `${heights[index]}%` }} /></div><span className="fm-bar-label">{key}</span></div>)}</div>;
}

export function AnimatedJobBars({ investigations }: Readonly<{ investigations: Record<string, number> }>) {
  return <ChartViewport className="fm-job-viewport"><JobBars investigations={investigations} /></ChartViewport>;
}
