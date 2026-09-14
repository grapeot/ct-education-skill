import assert from "node:assert/strict";
import test from "node:test";
import {
  createAppState,
  selectVoxel,
  setClip,
  setLayerOpacity,
  setLayerVisible,
  setTourStep,
  defaultLayerOpacity,
  defaultLayerVisible,
  expandTour,
  tourFallbackTitle,
  visibleLayerIds,
} from "../src/state.js";

function manifest() {
  return {
    schema_version: 1,
    shape: [8, 6, 10],
    spacing: [2, 1, 1],
    affine_lps: [
      [-1, 0, 0, 0],
      [0, -1, 0, 0],
      [0, 0, 2, 0],
      [0, 0, 0, 1],
    ],
    affine_ras: [
      [1, 0, 0, 0],
      [0, 1, 0, 0],
      [0, 0, 2, 0],
      [0, 0, 0, 1],
    ],
    bounds_ras: { min: [0, 0, 0], max: [9, 5, 14] },
    layers: [
      { id: "lungs", name: "Lungs", color: "#c4b5fd" },
      { id: "airways", name: "Airways", color: "#2ec9c0" },
      { id: "vessels", name: "Vessel candidates", color: "#e8b86d" },
    ],
    annotations: [
      {
        id: "c1",
        label: "Unverified candidate",
        position_ras: [4, 3, 8],
        radius_mm: 6,
        review_status: "unverified candidate",
      },
    ],
    warnings: ["synthetic warning"],
    source: { modality: "CT", slice_count: 8 },
    tour: [
      { id: "overview", title: "Volume Overview", layer_ids: ["lungs"], target_ras: [4, 2, 7] },
      { id: "source-evidence", layer_ids: ["lungs"], target_ras: [4, 3, 8], annotation_id: "c1" },
    ],
  };
}

test("initial selection indices sit at volume midplanes", () => {
  const state = createAppState(manifest());
  assert.equal(state.axis, "axial");
  assert.deepEqual(state.index, { axial: 4, coronal: 3, sagittal: 5 });
  assert.equal(state.tourIndex, -1);
  assert.equal(state.clip.enabled, false);
});

test("selecting a voxel drives all three native slice indices", () => {
  const next = selectVoxel(createAppState(manifest()), 2.2, 1.8, 6.4, manifest().shape);
  assert.equal(next.selection.error, null);
  assert.deepEqual([next.selection.i, next.selection.j, next.selection.k], [2, 2, 6]);
  assert.deepEqual(next.index, { axial: 6, coronal: 2, sagittal: 2 });
});

test("out-of-bounds selection is rejected and does not move slice indices", () => {
  const start = createAppState(manifest());
  const next = selectVoxel(start, 99, 0, 0, manifest().shape);
  assert.equal(next.selection.error, "outOfBounds");
  assert.deepEqual(next.index, start.index);
});

test("tour step stays in range and records the active stop", () => {
  const start = createAppState(manifest());
  assert.equal(setTourStep(start, 0, 2).tourIndex, 0);
  assert.equal(setTourStep(start, 2, 2).tourIndex, -1);
  assert.equal(setTourStep(start, -1, 2).tourIndex, -1);
});

test("hidden layers drop out of the visible set used for picking", () => {
  const start = createAppState(manifest());
  const hidden = setLayerVisible(start, "vessels", false);
  assert.deepEqual(visibleLayerIds(hidden), ["lungs", "airways"]);
  const faded = setLayerOpacity(hidden, "lungs", 0.4);
  assert.equal(faded.layers[0].opacity, 0.4);
});

test("clip state stores RAS axis and world value", () => {
  const next = setClip(createAppState(manifest()), { enabled: true, axis: "x", value: 3.5 });
  assert.equal(next.clip.enabled, true);
  assert.equal(next.clip.axis, "x");
  assert.equal(next.clip.value, 3.5);
});

test("tour fallback titles stay educational and non-diagnostic", () => {
  assert.equal(tourFallbackTitle("vascular-candidates"), "Vascular Candidate Geometry");
  assert.equal(tourFallbackTitle("case-candidate"), "Algorithmic Candidate Region");
  assert.equal(tourFallbackTitle("source-evidence"), "Native Slice Comparison");
});

test("minimal API tour is expanded with educational layer and source stops", () => {
  const data = manifest();
  data.tour = [
    { id: "overview", title: "Source-linked overview", layer_ids: ["lungs"], target_ras: [4, 2, 7] },
    { id: "tour-candidate-1", title: "Candidate 1", layer_ids: ["lungs"], target_ras: [4, 3, 8], annotation_id: "c1" },
  ];
  const stops = expandTour(data);
  const ids = stops.map((stop) => stop.id);
  assert.equal(stops[0].id, "overview");
  assert.ok(ids.includes("fallback-lungs"));
  assert.ok(ids.includes("fallback-airways"));
  assert.ok(ids.includes("fallback-vascular"));
  assert.equal(stops.find((stop) => stop.id === "tour-candidate-1").annotation_id, "c1");
  assert.ok(ids.includes("fallback-source-evidence"));
  assert.equal(defaultLayerOpacity("lungs"), 0.46);
  assert.equal(defaultLayerOpacity("airways"), 0.92);
  assert.equal(defaultLayerVisible("vessels"), false);
  assert.equal(defaultLayerVisible("lungs"), true);
});

test("complete API tour is kept without duplicate fallbacks", () => {
  const data = manifest();
  data.tour = [
    { id: "overview", title: "Volume Overview", layer_ids: ["lungs"], target_ras: [1, 1, 1] },
    { id: "lungs", title: "Lung Surface Geometry", layer_ids: ["lungs"], target_ras: [1, 1, 1] },
    { id: "airways", title: "Airway Geometry", layer_ids: ["airways"], target_ras: [1, 1, 1] },
    { id: "vascular-candidates", title: "Vascular Candidate Geometry", layer_ids: ["vessels"], target_ras: [1, 1, 1] },
    { id: "case-candidate", title: "Algorithmic Candidate Region", annotation_id: "c1", target_ras: [4, 3, 8] },
    { id: "source-evidence", title: "Native Slice Comparison", annotation_id: "c1", target_ras: [4, 3, 8] },
  ];
  const ids = expandTour(data).map((stop) => stop.id);
  assert.deepEqual(ids, [
    "overview",
    "lungs",
    "airways",
    "vascular-candidates",
    "case-candidate",
    "source-evidence",
  ]);
});
