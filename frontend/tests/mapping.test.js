import assert from "node:assert/strict";
import test from "node:test";
import { rasToVoxel, voxelToRas } from "../src/affine.js";
import {
  sliceCorners,
  sliceExtent,
  sliceOrientationLabels,
  slicePixelToVoxel,
  voxelToSlicePixel,
} from "../src/mapping.js";

const shape = [7, 5, 9];
const affineRas = [
  [1, 0, 0, 0],
  [0, 1, 0, 0],
  [0, 0, 1, 0],
  [0, 0, 0, 1],
];

test("native PNG pixel mapping uses raw i/j/k without flips", () => {
  assert.deepEqual(slicePixelToVoxel("axial", 3, 8, 4), { i: 8, j: 4, k: 3 });
  assert.deepEqual(slicePixelToVoxel("coronal", 2, 8, 6), { i: 8, j: 2, k: 6 });
  assert.deepEqual(slicePixelToVoxel("sagittal", 1, 4, 6), { i: 1, j: 4, k: 6 });
});

test("voxel to slice pixel inverts the native mapping", () => {
  const voxel = { i: 8, j: 4, k: 3 };
  assert.deepEqual(voxelToSlicePixel("axial", voxel), { col: 8, row: 4, index: 3 });
  assert.deepEqual(voxelToSlicePixel("coronal", voxel), { col: 8, row: 3, index: 4 });
  assert.deepEqual(voxelToSlicePixel("sagittal", voxel), { col: 4, row: 3, index: 8 });
});

test("slice extents follow volume[k,:,:], volume[:,j,:], volume[:,:,i]", () => {
  assert.deepEqual(sliceExtent("axial", shape), { width: 9, height: 5, maxIndex: 6 });
  assert.deepEqual(sliceExtent("coronal", shape), { width: 9, height: 7, maxIndex: 4 });
  assert.deepEqual(sliceExtent("sagittal", shape), { width: 5, height: 7, maxIndex: 8 });
});

test("slice corners come from the RAS affine, not a unit plane", () => {
  const corners = sliceCorners("axial", 3, shape, affineRas);
  assert.deepEqual(corners[0], voxelToRas(affineRas, 0, 0, 3));
  assert.deepEqual(corners[2], voxelToRas(affineRas, 8, 4, 3));
  const back = rasToVoxel(affineRas, corners[2]);
  assert.deepEqual(back.map((value) => Math.round(value)), [8, 4, 3]);
});

test("axial orientation labels use RAS physical axes", () => {
  const labels = sliceOrientationLabels("axial", 3, shape, affineRas);
  assert.equal(labels.mode, "ras");
  assert.equal(labels.left, "L");
  assert.equal(labels.right, "R");
  assert.equal(labels.top, "P");
  assert.equal(labels.bottom, "A");
});

test("oblique in-plane stretch falls back to source-axis labels", () => {
  const shear = [
    [1, 8, 0, 0],
    [0, 0.2, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];
  const labels = sliceOrientationLabels("axial", 1, shape, shear);
  assert.equal(labels.mode, "source-axis");
  assert.equal(labels.left, "i=0");
});
