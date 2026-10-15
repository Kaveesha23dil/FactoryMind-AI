"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { usePathname } from "next/navigation";

/** Animate presentation without remounting pages or restarting their workflows. */
export default function DashboardMotion({ children }: Readonly<{ children: ReactNode }>) {
  const root = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    const container = root.current;
    if (!container) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const selector = "section, article, .fm-metric, [role=tabpanel]";
    const seen = new WeakSet<Element>();
    let frame = 0;
    let entrance: Animation | undefined;
    if (!motion.matches) entrance = container.animate([{ opacity: 0.65 }, { opacity: 1 }], { duration: 260, easing: "ease-out" });
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const element = entry.target as HTMLElement;
        if (!motion.matches) element.classList.add("fm-reveal");
        observer.unobserve(element);
      }
    }, { threshold: 0.06 });
    function register() {
      if (!container) return;
      let index = 0;
      for (const element of container.querySelectorAll<HTMLElement>(selector)) {
        if (seen.has(element) || element.parentElement?.closest(selector)) continue;
        seen.add(element);
        element.style.setProperty("--fm-stagger", `${Math.min(index % 4, 3) * 65}ms`);
        observer.observe(element);
        index += 1;
      }
    }
    function schedule() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(register);
    }
    const mutations = new MutationObserver(schedule);
    mutations.observe(container, { childList: true, subtree: true });
    register();
    function finish(event: AnimationEvent) {
      if (event.animationName === "fm-panel-enter" && event.target instanceof HTMLElement) event.target.classList.remove("fm-reveal");
    }
    function reduceMotion() {
      if (!motion.matches) return;
      entrance?.cancel();
      container?.querySelectorAll(".fm-reveal").forEach(element => element.classList.remove("fm-reveal"));
    }
    container.addEventListener("animationend", finish);
    motion.addEventListener("change", reduceMotion);
    return () => {
      entrance?.cancel(); cancelAnimationFrame(frame); observer.disconnect(); mutations.disconnect();
      container.removeEventListener("animationend", finish);
      motion.removeEventListener("change", reduceMotion);
      container.querySelectorAll(".fm-reveal").forEach(element => element.classList.remove("fm-reveal"));
    };
  }, [pathname]);
  return <div ref={root} className="fm-motion-root">{children}</div>;
}
