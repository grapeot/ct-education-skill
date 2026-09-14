import { rasToVoxel } from "./affine.js";
import {
  inPlaneSpacing,
  pointPlaneDistance,
  sliceCorners,
  voxelToSlicePixel,
} from "./mapping.js";

export function eventToPixel(event, canvas) {
  const rect = canvas.getBoundingClientRect();
  const col = Math.round(((event.clientX - rect.left) / rect.width) * canvas.width);
  const row = Math.round(((event.clientY - rect.top) / rect.height) * canvas.height);
  return { col, row };
}

export function drawSliceView(target, source) {
  if (target.width !== source.width || target.height !== source.height) {
    target.width = source.width;
    target.height = source.height;
  }
  const context = target.getContext("2d");
  context.clearRect(0, 0, target.width, target.height);
  context.drawImage(source, 0, 0);
}

export function drawSliceOverlay(
  canvas,
  { sourceWidth, sourceHeight, pixel, annotations, axis, index, affineRas, shape },
) {
  if (canvas.width !== sourceWidth || canvas.height !== sourceHeight) {
    canvas.width = sourceWidth;
    canvas.height = sourceHeight;
  }
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  const corners = sliceCorners(axis, index, shape, affineRas);
  const spacing = inPlaneSpacing(axis, affineRas);
  for (const annotation of annotations || []) {
    const distance = pointPlaneDistance(annotation.position_ras, corners);
    if (distance > annotation.radius_mm) continue;
    const voxel = rasToVoxel(affineRas, annotation.position_ras);
    const projected = voxelToSlicePixel(axis, { i: voxel[0], j: voxel[1], k: voxel[2] });
    const rx = Math.max(annotation.radius_mm / Math.max(spacing.col, 1e-6), 2);
    const ry = Math.max(annotation.radius_mm / Math.max(spacing.row, 1e-6), 2);
    context.strokeStyle = "#e8b86d";
    context.lineWidth = 1.5;
    context.beginPath();
    context.ellipse(projected.col, projected.row, rx, ry, 0, 0, Math.PI * 2);
    context.stroke();
  }
  if (pixel) {
    context.strokeStyle = "#f3ead8";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(pixel.col + 0.5, 0);
    context.lineTo(pixel.col + 0.5, canvas.height);
    context.moveTo(0, pixel.row + 0.5);
    context.lineTo(canvas.width, pixel.row + 0.5);
    context.stroke();
    context.fillStyle = "#f3ead8";
    context.fillRect(pixel.col - 2, pixel.row - 2, 5, 5);
  }
}
