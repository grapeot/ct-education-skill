export function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function cloneMat4(matrix) {
  return matrix.map((row) => row.slice());
}

export function identity4() {
  return [
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1],
  ];
}

export function mat4Multiply(a, b) {
  const result = identity4();
  for (let i = 0; i < 4; i += 1) {
    for (let j = 0; j < 4; j += 1) {
      result[i][j] =
        a[i][0] * b[0][j] +
        a[i][1] * b[1][j] +
        a[i][2] * b[2][j] +
        a[i][3] * b[3][j];
    }
  }
  return result;
}

export function mat4MulVec(matrix, vector) {
  return [
    matrix[0][0] * vector[0] +
      matrix[0][1] * vector[1] +
      matrix[0][2] * vector[2] +
      matrix[0][3] * vector[3],
    matrix[1][0] * vector[0] +
      matrix[1][1] * vector[1] +
      matrix[1][2] * vector[2] +
      matrix[1][3] * vector[3],
    matrix[2][0] * vector[0] +
      matrix[2][1] * vector[1] +
      matrix[2][2] * vector[2] +
      matrix[2][3] * vector[3],
    matrix[3][0] * vector[0] +
      matrix[3][1] * vector[1] +
      matrix[3][2] * vector[2] +
      matrix[3][3] * vector[3],
  ];
}

export function invert4(matrix) {
  const a = cloneMat4(matrix);
  const inverse = identity4();
  for (let column = 0; column < 4; column += 1) {
    let pivot = column;
    for (let row = column + 1; row < 4; row += 1) {
      if (Math.abs(a[row][column]) > Math.abs(a[pivot][column])) {
        pivot = row;
      }
    }
    if (Math.abs(a[pivot][column]) < 1e-12) {
      throw new Error("singular");
    }
    if (pivot !== column) {
      [a[column], a[pivot]] = [a[pivot], a[column]];
      [inverse[column], inverse[pivot]] = [inverse[pivot], inverse[column]];
    }
    const divisor = a[column][column];
    for (let j = 0; j < 4; j += 1) {
      a[column][j] /= divisor;
      inverse[column][j] /= divisor;
    }
    for (let row = 0; row < 4; row += 1) {
      if (row === column) continue;
      const factor = a[row][column];
      for (let j = 0; j < 4; j += 1) {
        a[row][j] -= factor * a[column][j];
        inverse[row][j] -= factor * inverse[column][j];
      }
    }
  }
  return inverse;
}

export function lpsToRasPoint(lps) {
  return [-lps[0], -lps[1], lps[2]];
}

export function rasToLpsPoint(ras) {
  return [-ras[0], -ras[1], ras[2]];
}

export function voxelToRas(affineRas, i, j, k) {
  const homogeneous = mat4MulVec(affineRas, [i, j, k, 1]);
  return [homogeneous[0], homogeneous[1], homogeneous[2]];
}

export function rasToVoxel(affineRas, ras) {
  const inverse = invert4(affineRas);
  const homogeneous = mat4MulVec(inverse, [ras[0], ras[1], ras[2], 1]);
  return [homogeneous[0], homogeneous[1], homogeneous[2]];
}

export function roundVoxel(i, j, k, shape) {
  const ri = Math.round(i);
  const rj = Math.round(j);
  const rk = Math.round(k);
  const [nz, ny, nx] = shape;
  const inBounds =
    Number.isFinite(ri) &&
    Number.isFinite(rj) &&
    Number.isFinite(rk) &&
    ri >= 0 &&
    rj >= 0 &&
    rk >= 0 &&
    ri < nx &&
    rj < ny &&
    rk < nz;
  return {
    i: ri,
    j: rj,
    k: rk,
    inBounds,
    fractional: [i, j, k],
  };
}

export function affineAxisLengths(affine) {
  const axisLength = (col) =>
    Math.hypot(affine[0][col], affine[1][col], affine[2][col]);
  return {
    i: axisLength(0),
    j: axisLength(1),
    k: axisLength(2),
  };
}

export function subtract3(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

export function add3(a, b) {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

export function scale3(a, s) {
  return [a[0] * s, a[1] * s, a[2] * s];
}

export function length3(a) {
  return Math.hypot(a[0], a[1], a[2]);
}

export function formatNumber(value, digits = 1) {
  if (!isFiniteNumber(value)) return "--";
  return value.toFixed(digits);
}
