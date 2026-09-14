import assert from "node:assert/strict";
import test from "node:test";
import { firstUnclippedHit, shouldRejectClippedHit } from "../src/picking.js";

const plane = { normal: [0, 0, 1], constant: -10 };

test("clipped-away mesh hits are skipped in favor of the next kept hit", () => {
  const hits = [
    { point: [0, 0, 4], materialClipped: true, id: "clipped" },
    { point: [1, 0, 12], materialClipped: true, id: "kept" },
  ];
  const chosen = firstUnclippedHit(hits, plane, true);
  assert.equal(chosen.id, "kept");
});

test("slice or locator hits without clipping materials stay pickable", () => {
  const hits = [{ point: [0, 0, 4], materialClipped: false, id: "slice" }];
  const chosen = firstUnclippedHit(hits, plane, true);
  assert.equal(chosen.id, "slice");
});

test("disabled clip keeps the nearest hit even if it is on the discarded side", () => {
  const hits = [{ point: [0, 0, 4], materialClipped: true, id: "near" }];
  const chosen = firstUnclippedHit(hits, plane, false);
  assert.equal(chosen.id, "near");
  assert.equal(
    shouldRejectClippedHit({ clipEnabled: false, materialClipped: true, distance: -6 }),
    false,
  );
});

test("all clipped-away hits yield no selection", () => {
  const hits = [
    { point: [0, 0, 1], materialClipped: true },
    { point: [0, 0, 2], materialClipped: true },
  ];
  assert.equal(firstUnclippedHit(hits, plane, true), null);
  assert.equal(firstUnclippedHit([], plane, true), null);
});
