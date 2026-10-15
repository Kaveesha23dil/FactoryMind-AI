# Chart animation verification

Branch: `codex/chart-animations` (created before implementation). No commit or push.

## Scope

Next.js 16.4 / React 19.3 / Recharts 3.10.1. Sensor charts were explicitly static; overview used a whole-ring rotation and CSS bar scaling. The temperature comparison is a scatter plot and remains a scatter plot. No area series exists, so no gradient area was introduced. Layout, dimensions, colors, data and calculations are preserved.

Recharts supports native stroke drawing, previous-value interpolation, identity matching, custom interpolation and reduced-motion-aware `isAnimationActive="auto"`. These APIs are used instead of adding an animation dependency. [Recharts animations](https://recharts.github.io/en-US/guide/animations/).

- Sensor lines: 1400 ms ease-out native progressive stroke drawing; temporary point accents appear behind the measured draw position and fade out, preserving the existing dot-free final design. Active-dot and tooltip feedback remain available. Record IDs match successive datasets while existing sample labels remain unchanged.
- Recharts bars: 850 ms growth per bar with 85 ms stagger. A reusable native interpolation callback handles entrance, changed values, signed/horizontal feature bars, and removal. Existing radii/dimensions/colors and tooltip/cell behavior are retained.
- Overview donut: a 1200 ms clockwise SVG mask sweep starts at 12 o'clock. Center text stays stable. Existing legend/count labels fade in afterward. Updated sectors interpolate their values without replaying the entrance mask; hover gives a small emphasis.
- Overview bars: same 850/85 ms growth configuration; updates interpolate from the current displayed heights, including interrupted transitions.
- Viewport mounting reserves each chart's footprint and occurs only once. Scrolling away does not unmount it. Value-stable chart data prevents incidental rerenders/unchanged API responses from restarting native animation. Reduced motion disables custom RAF motion and uses Recharts' native accessibility behavior.

## Verification

- Four chart interpolation unit tests passed: stagger timing/final geometry, previous-value updates, signed baseline growth, and removal/null input. Four existing proxy tests also passed.
- Final type-check, lint, production build and all eight chart/proxy tests passed after the last interpolation adjustment. Node's existing module-type warning remains informational.
- Headless Edge with the real local dataset: donut sweep began below one and completed at one; center remained 580; search rerender did not replay the sweep or reset bar heights.
- Browser-only intercepted API responses tested updated donut sectors and job heights. The mask stayed complete while values interpolated. These test responses were not stored or presented as genuine new measurements.
- Sensor line stroke-dasharray grew from `0px` to a partial length and disappeared at completion, leaving the complete native path.
- Scrolling into the failure-category chart rendered five bars at their final dimensions. Native line and bar API updates each showed intermediate and final geometry rather than immediate replacement.
- An unchanged native API refresh produced zero stroke-dasharray mutations, confirming that the line entrance was not replayed. A reduced-motion sensor line rendered fully without a draw animation.
- Reduced-motion check: overview sweep was immediately complete, legend animation was `none`, and the mobile viewport had no horizontal overflow. No browser page errors occurred.

The initial browser attempt was affected by a repeatedly reloading development server. An isolated production server on another port was then blocked by the existing API CORS allowlist. Final browser checks used the normal trusted localhost:3000 origin; no CORS protection was weakened. Temporary preview servers were stopped and the normal development server restored at localhost:3000. Browser checks passed again on that server with no page errors. No Gemini requests, credentials, backend API changes, stored-record edits or cloud actions were part of these tests.

New reusable chart files: `chartAnimation.ts`, `ChartViewport.tsx`, `useChartMotion.ts`, `ProgressiveLine.tsx`, `AnimatedOverviewCharts.tsx`, and `chart-motion.css`. Existing sensor/bar chart components and the overview now use those helpers. Only obsolete chart animation rules were removed from the shared motion stylesheet; unrelated dashboard animations remain intact.
