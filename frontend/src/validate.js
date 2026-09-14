import { isFiniteNumber, length3, subtract3 } from "./affine.js";

function fail(code) {
  return { ok: false, code };
}

function isMat4(matrix) {
  return (
    Array.isArray(matrix) &&
    matrix.length === 4 &&
    matrix.every(
      (row) =>
        Array.isArray(row) &&
        row.length === 4 &&
        row.every((value) => isFiniteNumber(value)),
    )
  );
}

function isVec3(vector) {
  return Array.isArray(vector) && vector.length === 3 && vector.every(isFiniteNumber);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.length > 0;
}

export function validateManifest(data) {
  if (!data || typeof data !== "object") return fail("invalidManifest");
  if (data.schema_version !== 1) return fail("invalidManifest");
  if (!Array.isArray(data.shape) || data.shape.length !== 3) return fail("invalidManifest");
  const [nz, ny, nx] = data.shape;
  if (![nz, ny, nx].every((value) => Number.isInteger(value) && value > 0)) {
    return fail("invalidManifest");
  }
  if (
    !Array.isArray(data.spacing) ||
    data.spacing.length !== 3 ||
    !data.spacing.every((value) => isFiniteNumber(value) && value > 0)
  ) {
    return fail("invalidManifest");
  }
  if (!isMat4(data.affine_lps) || !isMat4(data.affine_ras)) return fail("invalidManifest");
  if (
    !data.bounds_ras ||
    !isVec3(data.bounds_ras.min) ||
    !isVec3(data.bounds_ras.max)
  ) {
    return fail("invalidManifest");
  }
  const extent = subtract3(data.bounds_ras.max, data.bounds_ras.min);
  if (extent.some((value) => !isFiniteNumber(value))) return fail("invalidManifest");
  if (!Array.isArray(data.layers)) return fail("invalidManifest");
  const ids = new Set();
  for (const layer of data.layers) {
    if (!layer || !isNonEmptyString(layer.id) || ids.has(layer.id)) return fail("invalidManifest");
    ids.add(layer.id);
    if (layer.name != null && typeof layer.name !== "string") return fail("invalidManifest");
    if (layer.color != null && typeof layer.color !== "string") return fail("invalidManifest");
    if (layer.description != null && typeof layer.description !== "string") {
      return fail("invalidManifest");
    }
    if (layer.review_status != null && typeof layer.review_status !== "string") {
      return fail("invalidManifest");
    }
    if (layer.mesh != null && typeof layer.mesh !== "string") return fail("invalidManifest");
  }
  if (!Array.isArray(data.annotations)) return fail("invalidManifest");
  for (const annotation of data.annotations) {
    if (!annotation || !isNonEmptyString(annotation.id)) return fail("invalidManifest");
    if (!isVec3(annotation.position_ras)) return fail("invalidManifest");
    if (!isFiniteNumber(annotation.radius_mm) || annotation.radius_mm < 0) {
      return fail("invalidManifest");
    }
    if (annotation.label != null && typeof annotation.label !== "string") {
      return fail("invalidManifest");
    }
    if (annotation.description != null && typeof annotation.description !== "string") {
      return fail("invalidManifest");
    }
    if (annotation.review_status != null && typeof annotation.review_status !== "string") {
      return fail("invalidManifest");
    }
  }
  if (data.warnings != null) {
    if (!Array.isArray(data.warnings) || data.warnings.some((item) => typeof item !== "string")) {
      return fail("invalidManifest");
    }
  }
  if (!data.source || typeof data.source !== "object") return fail("invalidManifest");
  if (!Number.isInteger(data.source.slice_count) || data.source.slice_count < 0) {
    return fail("invalidManifest");
  }
  if (data.tour != null) {
    if (!Array.isArray(data.tour)) return fail("invalidManifest");
    for (const stop of data.tour) {
      if (!stop || !isNonEmptyString(stop.id)) return fail("invalidManifest");
      if (stop.title != null && typeof stop.title !== "string") return fail("invalidManifest");
      if (stop.description != null && typeof stop.description !== "string") {
        return fail("invalidManifest");
      }
      if (stop.layer_ids != null && !Array.isArray(stop.layer_ids)) return fail("invalidManifest");
      if (stop.target_ras != null && !isVec3(stop.target_ras)) return fail("invalidManifest");
      if (stop.annotation_id != null && typeof stop.annotation_id !== "string") {
        return fail("invalidManifest");
      }
    }
  }
  if (data.source.slice_count === 0 && data.layers.length === 0) return fail("noData");
  return { ok: true };
}

export function validateMesh(data, boundsRas) {
  if (!data || typeof data !== "object") return fail("invalidMesh");
  if (!Array.isArray(data.positions) || !Array.isArray(data.indices)) return fail("invalidMesh");
  if (data.positions.length === 0 || data.positions.length % 3 !== 0) return fail("invalidMesh");
  if (data.indices.length === 0 || data.indices.length % 3 !== 0) return fail("invalidMesh");
  const vertexCount = data.positions.length / 3;
  for (let i = 0; i < data.positions.length; i += 1) {
    if (!isFiniteNumber(data.positions[i])) return fail("invalidMesh");
  }
  for (let i = 0; i < data.indices.length; i += 1) {
    const index = data.indices[i];
    if (!Number.isInteger(index) || index < 0 || index >= vertexCount) return fail("invalidMesh");
  }
  if (boundsRas && isVec3(boundsRas.min) && isVec3(boundsRas.max)) {
    const diagonal = length3(subtract3(boundsRas.max, boundsRas.min));
    const limit = Math.max(diagonal * 10, 1);
    const center = [
      (boundsRas.min[0] + boundsRas.max[0]) / 2,
      (boundsRas.min[1] + boundsRas.max[1]) / 2,
      (boundsRas.min[2] + boundsRas.max[2]) / 2,
    ];
    for (let i = 0; i < vertexCount; i += 1) {
      const point = [
        data.positions[i * 3],
        data.positions[i * 3 + 1],
        data.positions[i * 3 + 2],
      ];
      if (length3(subtract3(point, center)) > limit) return fail("invalidMesh");
    }
  }
  return {
    ok: true,
    vertexCount,
    triangleCount: data.indices.length / 3,
  };
}

export function isCssHexColor(value) {
  return typeof value === "string" && /^#[0-9A-Fa-f]{6}$/.test(value);
}
