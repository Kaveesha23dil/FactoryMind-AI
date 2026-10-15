"use client";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { easeOut } from "./chartAnimation";

function subscribe(callback: () => void) {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
const reducedSnapshot = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
export const useReducedChartMotion = () => useSyncExternalStore(subscribe, reducedSnapshot, () => true);

/** Numeric/string chart data is small; value identity prevents incidental rerenders from replaying. */
export function useChartData<T>(data: T): T {
  const serialized = JSON.stringify(data);
  return useMemo(() => JSON.parse(serialized) as T, [serialized]);
}

/** Only the custom four-sector/four-bar overview charts need a React frame clock. */
export function useAnimatedNumbers(values: number[], duration: number, fromZero = true, stagger = 0) {
  const target = useChartData(values);
  const reduced = useReducedChartMotion();
  const [displayed, setDisplayed] = useState(() => fromZero ? target.map(() => 0) : target);
  const previous = useRef(displayed);
  useEffect(() => {
    if (reduced) { previous.current = target; return; }
    const startValues = previous.current;
    let frame = 0;
    let start: number | undefined;
    const total = duration + Math.max(0, target.length - 1) * stagger;
    function tick(now: number) {
      start ??= now;
      const elapsed = now - start;
      const next = target.map((value, index) => {
        const progress = easeOut((elapsed - index * stagger) / duration);
        return (startValues[index] ?? 0) + (value - (startValues[index] ?? 0)) * progress;
      });
      previous.current = next;
      setDisplayed(next);
      if (elapsed < total) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, reduced, stagger]);
  return reduced ? target : displayed;
}
