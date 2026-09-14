import { affineAxisLengths, length3, subtract3, voxelToRas } from "./affine.js";

export const AXES = ["axial", "coronal", "sagittal"];

export function sliceExtent(axis, shape) {
  const [nz, ny, nx] = shape;
  if (axis === "axial") return { width: nx, height: ny, maxIndex: nz - 1 };
  if (axis === "coronal") return { width: nx, height: nz, maxIndex: ny - 1 };
  return { width: ny, height: nz, maxIndex: nx - 1 };
}

export function clampIndex(index, maxIndex) {
  if (!Number.isFinite(index)) return 0;
  return Math.min(maxIndex, Math.max(0, Math.round(index)));
}

export function slicePixelToVoxel(axis, index, col, row) {
  if (axis === "axial") return { i: col, j: row, k: index };
  if (axis === "coronal") return { i: col, j: index, k: row };
  return { i: index, j: col, k: row };
}

export function voxelToSlicePixel(axis, voxel) {
  if (axis === "axial") {
    return { col: voxel.i, row: voxel.j, index: voxel.k };
  }
  if (axis === "coronal") {
    return { col: voxel.i, row: voxel.k, index: voxel.j };
  }
  return { col: voxel.j, row: voxel.k, index: voxel.i };
}

export function sliceCorners(axis, index, shape, affineRas) {
  const [nz, ny, nx] = shape;
  const i1 = Math.max(0, nx - 1);
  const j1 = Math.max(0, ny - 1);
  const k1 = Math.max(0, nz - 1);
  if (axis === "axial") {
    return [
      voxelToRas(affineRas, 0, 0, index),
      voxelToRas(affineRas, i1, 0, index),
      voxelToRas(affineRas, i1, j1, index),
      voxelToRas(affineRas, 0, j1, index),
    ];
  }
  if (axis === "coronal") {
    return [
      voxelToRas(affineRas, 0, index, 0),
      voxelToRas(affineRas, i1, index, 0),
      voxelToRas(affineRas, i1, index, k1),
      voxelToRas(affineRas, 0, index, k1),
    ];
  }
  return [
    voxelToRas(affineRas, index, 0, 0),
    voxelToRas(affineRas, index, j1, 0),
    voxelToRas(affineRas, index, j1, k1),
    voxelToRas(affineRas, index, 0, k1),
  ];
}

export function rasDirectionLabel(delta) {
  const ax = Math.abs(delta[0]);
  const ay = Math.abs(delta[1]);
  const az = Math.abs(delta[2]);
  const max = Math.max(ax, ay, az);
  if (max < 1e-8) return null;
  if (ax === max) return delta[0] >= 0 ? "R" : "L";
  if (ay === max) return delta[1] >= 0 ? "A" : "P";
  return delta[2] >= 0 ? "S" : "I";
}

export function sourceAxisLabels(axis) {
  if (axis === "axial") {
    return { left: "i=0", right: "i+", top: "j=0", bottom: "j+" };
  }
  if (axis === "coronal") {
    return { left: "i=0", right: "i+", top: "k=0", bottom: "k+" };
  }
  return { left: "j=0", right: "j+", top: "k=0", bottom: "k+" };
}

export function sliceOrientationLabels(axis, index, shape, affineRas) {
  const [nz, ny, nx] = shape;
  const midI = (nx - 1) / 2;
  const midJ = (ny - 1) / 2;
  const midK = (nz - 1) / 2;
  let center;
  let left;
  let right;
  let top;
  let bottom;
  if (axis === "axial") {
    center = voxelToRas(affineRas, midI, midJ, index);
    left = voxelToRas(affineRas, 0, midJ, index);
    right = voxelToRas(affineRas, nx - 1, midJ, index);
    top = voxelToRas(affineRas, midI, 0, index);
    bottom = voxelToRas(affineRas, midI, ny - 1, index);
  } else if (axis === "coronal") {
    center = voxelToRas(affineRas, midI, index, midK);
    left = voxelToRas(affineRas, 0, index, midK);
    right = voxelToRas(affineRas, nx - 1, index, midK);
    top = voxelToRas(affineRas, midI, index, 0);
    bottom = voxelToRas(affineRas, midI, index, nz - 1);
  } else {
    center = voxelToRas(affineRas, index, midJ, midK);
    left = voxelToRas(affineRas, index, 0, midK);
    right = voxelToRas(affineRas, index, ny - 1, midK);
    top = voxelToRas(affineRas, index, midJ, 0);
    bottom = voxelToRas(affineRas, index, midJ, nz - 1);
  }
  const leftDelta = subtract3(left, center);
  const rightDelta = subtract3(right, center);
  const topDelta = subtract3(top, center);
  const bottomDelta = subtract3(bottom, center);
  const lengths = [leftDelta, rightDelta, topDelta, bottomDelta].map(length3);
  const longest = Math.max(...lengths, 1e-8);
  const ambiguous = lengths.some((value) => value > 1e-8 && value / longest < 0.35);
  if (ambiguous) {
    return { ...sourceAxisLabels(axis), mode: "source-axis" };
  }
  const labels = {
    left: rasDirectionLabel(leftDelta),
    right: rasDirectionLabel(rightDelta),
    top: rasDirectionLabel(topDelta),
    bottom: rasDirectionLabel(bottomDelta),
    mode: "ras",
  };
  if (!labels.left || !labels.right || !labels.top || !labels.bottom) {
    return { ...sourceAxisLabels(axis), mode: "source-axis" };
  }
  return labels;
}

export function inPlaneSpacing(axis, affineRas) {
  const lengths = affineAxisLengths(affineRas);
  if (axis === "axial") return { col: lengths.i, row: lengths.j };
  if (axis === "coronal") return { col: lengths.i, row: lengths.k };
  return { col: lengths.j, row: lengths.k };
}

export function pointPlaneDistance(point, corners) {
  const [a, b, d] = corners;
  const ab = subtract3(b, a);
  const ad = subtract3(d, a);
  const nx = ab[1] * ad[2] - ab[2] * ad[1];
  const ny = ab[2] * ad[0] - ab[0] * ad[2];
  const nz = ab[0] * ad[1] - ab[1] * ad[0];
  const normalLength = Math.hypot(nx, ny, nz);
  if (normalLength < 1e-8) return Infinity;
  const dx = point[0] - a[0];
  const dy = point[1] - a[1];
  const dz = point[2] - a[2];
  return Math.abs(nx * dx + ny * dy + nz * dz) / normalLength;
}
