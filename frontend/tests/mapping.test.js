import assert from "node:assert/strict";
import test from "node:test";
import { rasToVoxel, voxelToRas } from "../src/affine.js";
import {
  displayPixelToVoxel,
  displayRowToNative,
  nativeRowToDisplay,
  shouldFlipDisplayRows,
  sliceCorners,
  sliceDisplayOrientationLabels,
  sliceExtent,
  slicePhysicalAspect,
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

test("coronal and sagittal CSS aspect uses affine spacing not square pixels", () => {
  const spaced = [
    [0.75, 0, 0, 0],
    [0, 0.75, 0, 0],
    [0, 0, 0.625, 0],
    [0, 0, 0, 1],
  ];
  const volume = [564, 512, 512];
  const aspect = slicePhysicalAspect("coronal", volume, spaced);
  assert.ok(Math.abs(aspect - (512 * 0.75) / (564 * 0.625)) < 1e-12);
  const cssHeight = 242 / aspect;
  assert.ok(Math.abs(cssHeight - 222.15) < 0.02);
  assert.ok(slicePhysicalAspect("sagittal", volume, spaced) > 0);
});

test("coronal display flips rows so superior is up without changing native PNG mapping", () => {
  assert.equal(shouldFlipDisplayRows("axial", affineRas), false);
  assert.equal(shouldFlipDisplayRows("coronal", affineRas), true);
  assert.equal(shouldFlipDisplayRows("sagittal", affineRas), true);
  assert.deepEqual(slicePixelToVoxel("coronal", 2, 8, 0), { i: 8, j: 2, k: 0 });
  assert.deepEqual(displayPixelToVoxel("coronal", 2, 8, 0, 7, true), { i: 8, j: 2, k: 6 });
  assert.equal(nativeRowToDisplay(0, 7, true), 6);
  assert.equal(displayRowToNative(6, 7, true), 0);
});

test("flipped coronal labels put superior at the top of the 2D display", () => {
  const native = sliceOrientationLabels("coronal", 2, shape, affineRas);
  assert.equal(native.top, "I");
  assert.equal(native.bottom, "S");
  const display = sliceDisplayOrientationLabels("coronal", 2, shape, affineRas, true);
  assert.equal(display.top, "S");
  assert.equal(display.bottom, "I");
  assert.equal(display.left, native.left);
  assert.equal(display.right, native.right);
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
