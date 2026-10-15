import type { AnimationInterpolateFn, BarRectangleItem } from "recharts";

export const CHART_MOTION = { line: 1400, bar: 850, stagger: 85, pie: 1200 } as const;
export const LINE_ANIMATION = { isAnimationActive: "auto", animationDuration: CHART_MOTION.line, animationEasing: "ease-out" } as const;
export const easeOut = (progress: number) => 1 - (1 - Math.max(0, Math.min(1, progress))) ** 3;
export const staggerDuration = (count: number) => CHART_MOTION.bar + Math.max(0, count - 1) * CHART_MOTION.stagger;
const interpolate = (from: number, to: number, progress: number) => from + (to - from) * progress;

/** Recharts owns the frame clock and preserves interrupted animation snapshots. */
export const staggeredBars: AnimationInterpolateFn<BarRectangleItem, "horizontal" | "vertical"> = (items, elapsed, layout) => {
  if (!items) return [];
  if (elapsed >= 1) return items.flatMap(item => item.status === "removed" ? [] : [item.next]);
  const duration = staggerDuration(items.filter(item => item.status !== "removed").length);
  let visibleIndex = 0;
  return items.map(item => {
    const delay = item.status === "removed" ? 0 : visibleIndex++ * CHART_MOTION.stagger;
    const progress = easeOut((elapsed * duration - delay) / CHART_MOTION.bar);
    const target = item.status === "removed" ? item.prev : item.next;
    const collapsed = layout === "horizontal"
      ? { ...target, height: 0, y: target.stackedBarStart }
      : { ...target, width: 0, x: target.stackedBarStart };
    const from = item.status === "added" ? collapsed : item.prev;
    const to = item.status === "removed" ? collapsed : target;
    return { ...target, x: interpolate(from.x, to.x, progress), y: interpolate(from.y, to.y, progress),
      width: interpolate(from.width, to.width, progress), height: interpolate(from.height, to.height, progress) };
  });
};

export const barAnimation = (count: number) => ({
  isAnimationActive: "auto" as const, animationDuration: staggerDuration(count), animationEasing: "linear" as const,
  animationInterpolateFn: staggeredBars,
});
