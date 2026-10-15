"use client";
import { LineDrawShape, type LineDrawShapeProps } from "recharts";
import { useLayoutEffect, useRef } from "react";

/** Preserve the native stroke draw; reveal temporary point accents behind its measured path. */
export default function ProgressiveLine(props: LineDrawShapeProps) {
  const { points = [], isEntrance, isAnimating, animationElapsedTime = 1, pathRef, visibleLength } = props;
  const accents = useRef<SVGGElement>(null);
  useLayoutEffect(() => {
    const path = pathRef.current;
    if (!isEntrance || !isAnimating || !path || visibleLength == null) return;
    const visible = path.getPointAtLength(visibleLength).x;
    accents.current?.querySelectorAll("circle").forEach(dot => {
      const opacity = Number(dot.getAttribute("cx")) <= visible ? Math.min(1, (1 - animationElapsedTime) * 5) : 0;
      dot.setAttribute("opacity", String(opacity));
    });
  }, [pathRef, visibleLength, isEntrance, isAnimating, animationElapsedTime]);
  return <g><LineDrawShape {...props} /><g ref={accents} aria-hidden="true">{isEntrance && isAnimating && points.map((point, index) => {
    if (point.x == null || point.y == null) return null;
    return <circle key={index} cx={point.x} cy={point.y} r={1.5} fill={props.stroke} opacity={0} pointerEvents="none" />;
  })}</g></g>;
}
