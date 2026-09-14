export function planeDistance(plane, point) {
  return (
    plane.normal[0] * point[0] +
    plane.normal[1] * point[1] +
    plane.normal[2] * point[2] +
    plane.constant
  );
}

export function shouldRejectClippedHit({ clipEnabled, materialClipped, distance, epsilon = 1e-4 }) {
  return Boolean(clipEnabled && materialClipped && distance < -epsilon);
}

export function firstUnclippedHit(hits, plane, clipEnabled) {
  if (!Array.isArray(hits) || hits.length === 0) return null;
  for (const hit of hits) {
    const point = Array.isArray(hit.point)
      ? hit.point
      : [hit.point.x, hit.point.y, hit.point.z];
    const distance = plane ? planeDistance(plane, point) : 0;
    if (
      shouldRejectClippedHit({
        clipEnabled,
        materialClipped: Boolean(hit.materialClipped),
        distance,
      })
    ) {
      continue;
    }
    return hit;
  }
  return null;
}
