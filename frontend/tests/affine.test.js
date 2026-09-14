import assert from "node:assert/strict";
import test from "node:test";
import {
  invert4,
  lpsToRasPoint,
  mat4MulVec,
  mat4Multiply,
  rasToLpsPoint,
  rasToVoxel,
  roundVoxel,
  voxelToRas,
} from "../src/affine.js";
import { validateManifest, validateMesh } from "../src/validate.js";

const affineRas = [
  [1.5, 0, 0, 10],
  [0, 1.25, 0, 20],
  [0, 0, 2, 30],
  [0, 0, 0, 1],
];

test("voxel centers map through RAS affine", () => {
  const ras = voxelToRas(affineRas, 2, 4, 6);
  assert.deepEqual(ras, [13, 25, 42]);
});

test("RAS to voxel inverts the affine", () => {
  const voxel = rasToVoxel(affineRas, [13, 25, 42]);
  assert.ok(Math.abs(voxel[0] - 2) < 1e-10);
  assert.ok(Math.abs(voxel[1] - 4) < 1e-10);
  assert.ok(Math.abs(voxel[2] - 6) < 1e-10);
});

test("LPS and RAS differ by the viewer diag(-1,-1,1) map", () => {
  assert.deepEqual(lpsToRasPoint([-13, -25, 42]), [13, 25, 42]);
  assert.deepEqual(rasToLpsPoint([13, 25, 42]), [-13, -25, 42]);
});

test("inverse affine multiplied by affine is identity", () => {
  const inverse = invert4(affineRas);
  const product = mat4Multiply(inverse, affineRas);
  for (let i = 0; i < 4; i += 1) {
    for (let j = 0; j < 4; j += 1) {
      const expected = i === j ? 1 : 0;
      assert.ok(Math.abs(product[i][j] - expected) < 1e-10);
    }
  }
});

test("homogeneous multiply preserves translation", () => {
  const result = mat4MulVec(affineRas, [0, 0, 0, 1]);
  assert.deepEqual(result.slice(0, 3), [10, 20, 30]);
});

test("nearest voxel rejects out of bounds without clamping", () => {
  const inside = roundVoxel(1.4, 2.6, 0.1, [8, 8, 8]);
  assert.equal(inside.inBounds, true);
  assert.deepEqual([inside.i, inside.j, inside.k], [1, 3, 0]);
  const outside = roundVoxel(-0.6, 2, 2, [8, 8, 8]);
  assert.equal(outside.inBounds, false);
  assert.equal(outside.i, -1);
});

test("manifest schema rejects missing version and non-finite affine", () => {
  const base = {
    schema_version: 1,
    shape: [4, 5, 6],
    spacing: [2, 1, 1],
    affine_lps: affineRas,
    affine_ras: affineRas,
    bounds_ras: { min: [0, 0, 0], max: [10, 10, 10] },
    layers: [{ id: "lungs", name: "Lungs", color: "#c4b5fd" }],
    annotations: [],
    warnings: [],
    source: { modality: "CT", slice_count: 4 },
    tour: [],
  };
  assert.equal(validateManifest(base).ok, true);
  assert.equal(validateManifest({ ...base, schema_version: 2 }).ok, false);
  const badAffine = structuredClone(base);
  badAffine.affine_ras[0][0] = Infinity;
  assert.equal(validateManifest(badAffine).code, "invalidManifest");
});

test("mesh validation requires finite positions, triangles, and bounds", () => {
  const mesh = {
    positions: [0, 0, 0, 1, 0, 0, 0, 1, 0],
    indices: [0, 1, 2],
  };
  const bounds = { min: [0, 0, 0], max: [2, 2, 2] };
  assert.equal(validateMesh(mesh, bounds).ok, true);
  assert.equal(validateMesh({ positions: [0, 0, Number.NaN], indices: [0, 0, 0] }, bounds).ok, false);
  assert.equal(
    validateMesh({ positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], indices: [0, 1, 9] }, bounds).ok,
    false,
  );
  assert.equal(
    validateMesh({ positions: [0, 0, 0, 1000, 0, 0, 0, 1000, 0], indices: [0, 1, 2] }, bounds).ok,
    false,
  );
});
