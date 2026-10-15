"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import "./chart-motion.css";

/** Keep a fixed chart footprint, mount once on first entry, never remount for data updates. */
export default function ChartViewport({ children, className }: Readonly<{ children: ReactNode; className: string }>) {
  const root = useRef<HTMLDivElement>(null);
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    if (!root.current) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setEntered(true); observer.disconnect(); }
    }, { threshold: 0.08 });
    observer.observe(root.current);
    return () => observer.disconnect();
  }, []);
  return <div ref={root} className={className} data-chart-viewport={entered ? "entered" : "waiting"}>{entered ? children : null}</div>;
}
