import test from "node:test";
import assert from "node:assert/strict";
import { CHART_MOTION, staggerDuration, staggeredBars } from "../src/components/charts/chartAnimation.ts";

const bar = (x, y, width, height, baseline = 100) => ({ x, y, width, height, stackedBarStart: baseline });
test("bars enter sequentially and preserve their final geometry", () => {
  const items = [0, 1, 2].map(index => ({ status: "added", next: bar(index * 30, 20, 20, 80) }));
  const early = staggeredBars(items, 40 / staggerDuration(items.length), "horizontal");
  assert.ok(early[0].height > 0);
  assert.equal(early[1].height, 0);
  assert.equal(early[2].height, 0);
  assert.equal(early[0].y + early[0].height, 100);
  assert.deepEqual(staggeredBars(items, 1, "horizontal"), items.map(item => item.next));
  assert.equal(CHART_MOTION.stagger, 85);
});
test("changed bars interpolate from previous values, not zero", () => {
  const item = { status: "matched", prev: bar(0, 60, 20, 40), next: bar(0, 20, 20, 80) };
  const before = structuredClone(item);
  const [step] = staggeredBars([item], 0.5, "horizontal");
  assert.ok(step.height > 40 && step.height < 80);
  assert.deepEqual(item, before);
  assert.deepEqual(staggeredBars([item], 0, "horizontal")[0], item.prev);
});
test("horizontal and negative feature bars grow from their actual zero baseline", () => {
  const positive = { status: "added", next: bar(100, 10, 60, 15) };
  const negative = { status: "added", next: bar(40, 30, 60, 15) };
  const start = staggeredBars([positive, negative], 0, "vertical");
  assert.equal(start[0].x, 100); assert.equal(start[1].x, 100);
  assert.equal(start[0].width, 0); assert.equal(start[1].width, 0);
  assert.deepEqual(staggeredBars([positive, negative], 1, "vertical"), [positive.next, negative.next]);
});
test("removed values collapse and disappear without corrupting surviving bars", () => {
  const previous = bar(0, 20, 20, 80);
  assert.ok(staggeredBars([{ status: "removed", prev: previous }], 0.5, "horizontal")[0].height < 80);
  assert.deepEqual(staggeredBars([{ status: "removed", prev: previous }], 1, "horizontal"), []);
  assert.deepEqual(staggeredBars(null, 0, "horizontal"), []);
});
