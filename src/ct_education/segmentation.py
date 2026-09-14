"""Bounded-memory CPU heuristics, never diagnostic or exhaustive anatomy."""

import numpy as np
from scipy import ndimage as ndi
from skimage.measure import marching_cubes


LAYER_INFO = {
    "lungs": ("Lung candidates", "#65c8cc", "Thresholded interior air envelopes; disease and incomplete coverage can cause omissions."),
    "airways": ("Airway candidates", "#ecc071", "Connected low-HU candidate seeded in a superior central air pocket; not all branches."),
    "vessels": ("Dense intrapulmonary candidates", "#e78383", "Dense structures inside eroded lung envelopes; may include nonvascular tissue. No artery/vein classification."),
    "bones": ("Bone candidates", "#d9d2bc", "High-HU body components; may include calcifications and other dense material."),
}


def components(mask, minimum=1, keep=None, structure=None):
    labels, count = ndi.label(mask, structure=structure)
    if not count:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    chosen = np.flatnonzero(sizes >= minimum)
    chosen = chosen[chosen != 0]
    if keep is not None:
        chosen = chosen[np.argsort(sizes[chosen])[-keep:]]
    lookup = np.zeros(count + 1, dtype=bool)
    lookup[chosen] = True
    return lookup[labels]


def physical_disk(spacing_ji, radius_mm):
    extent = np.ceil(radius_mm / np.asarray(spacing_ji)).astype(int)
    j, i = np.ogrid[-extent[0]:extent[0] + 1, -extent[1]:extent[1] + 1]
    return (j * spacing_ji[0]) ** 2 + (i * spacing_ji[1]) ** 2 <= radius_mm ** 2


def airway_candidates(reduced, body, affine):
    spacing = np.linalg.norm(affine[:3, :3], axis=0)[::-1]
    area = float(np.linalg.norm(np.cross(affine[:3, 0], affine[:3, 1])))
    voxel_size = abs(float(np.linalg.det(affine[:3, :3])))
    allowed = np.zeros(reduced.shape, dtype=bool)
    conservative = np.zeros_like(allowed)
    seed_regions = np.zeros_like(allowed)
    in_plane = np.ones((3, 3), dtype=bool)
    connectivity = np.ones((3, 3, 3), dtype=bool)
    bulk_footprint = physical_disk(spacing[1:], 4.0)
    for k, plane in enumerate(reduced):
        coords = np.argwhere(body[k])
        if not coords.size:
            continue
        lo, hi = coords.min(axis=0), coords.max(axis=0)
        center = (lo + hi) / 2
        # Face-connected pockets avoid merging across a diagonal wall contact;
        # propagation between accepted pockets still uses all 26 neighbors.
        labels, count = ndi.label(body[k] & (plane < -850))
        if not count:
            continue
        sizes = np.bincount(labels.ravel()) * area
        # Reject components in the bulk lung, including fragmented low-HU pockets.
        bulk_air = ndi.binary_opening(body[k] & (plane < -450), structure=bulk_footprint)
        bulk = components(bulk_air, minimum=max(1, int(1000 / area)), structure=in_plane)
        bulk_core = ndi.binary_erosion(bulk, structure=bulk_footprint)
        for obj_index, region in enumerate(ndi.find_objects(labels), 1):
            if region is None or not 2 <= sizes[obj_index] <= 600:
                continue
            midpoint = np.array([(s.start + s.stop - 1) / 2 for s in region])
            width_mm = np.array([s.stop - s.start for s in region]) * spacing[1:]
            if np.any(np.abs(midpoint - center) > (hi - lo) * 0.35) or width_mm.max() > 50:
                continue
            pocket = labels[region] == obj_index
            if np.count_nonzero(pocket & bulk_core[region]) > 0.9 * np.count_nonzero(pocket):
                continue
            allowed[k][region] |= pocket
            central = np.all(np.abs(midpoint - center) <= (hi - lo) * np.array([0.3, 0.2]))
            if central and 5 <= sizes[obj_index] <= 250:
                conservative[k][region] |= pocket
            if central and 5 <= sizes[obj_index] <= 350 and np.median(plane[region][pocket]) < -900:
                seed_regions[k][region] |= pocket
    superior_order = range(len(reduced) - 1, -1, -1) if affine[2, 2] > 0 else range(len(reduced))
    seed = np.zeros_like(allowed)
    for rank, k in enumerate(superior_order):
        if rank >= max(1, len(reduced) // 3):
            break
        if seed_regions[k].any():
            seed[k] = components(seed_regions[k], keep=1, structure=in_plane)
            break
    messages = []
    if not seed.any():
        return seed, ["airways: no supported superior seed; no branches inferred."]
    airway = ndi.binary_propagation(seed, mask=allowed, structure=connectivity)
    if airway.sum() * voxel_size > 80_000 or airway.sum(axis=(1, 2)).max() * area > 800:
        messages.append("airways: growth exceeded conservative volume or cross-section limits; broader growth discarded.")
        safe_seed = seed & conservative
        airway = ndi.binary_propagation(safe_seed, mask=conservative, structure=connectivity) if safe_seed.any() else np.zeros_like(seed)
        if airway.sum() * voxel_size > 80_000 or airway.sum(axis=(1, 2)).max() * area > 800:
            airway[:] = False
    airway = components(airway, minimum=max(4, int(20 / voxel_size)), keep=1, structure=connectivity)
    split_run = longest_run = 0
    for plane in airway:
        split_run = split_run + 1 if ndi.label(plane, structure=in_plane)[1] >= 2 else 0
        longest_run = max(longest_run, split_run)
    if longest_run * spacing[0] < 6:
        messages.append("airways: no sustained bifurcation recovered; conservative candidate only, not evidence that branches are absent.")
    messages.append("airways: growth stops at large or inseparable air pockets; branch identity and completeness remain unverified.")
    return airway, messages


def segment(volume, affine):
    spacing = np.linalg.norm(affine[:3, :3], axis=0)[::-1]
    stride = np.maximum(1, np.maximum(np.ceil(np.asarray(volume.shape) / 192), np.floor(1.5 / spacing))).astype(int)
    reduced = np.asarray(volume[::stride[0], ::stride[1], ::stride[2]], dtype=np.float32)
    label_affine = affine @ np.diag([*stride[::-1], 1])
    masks = {name: np.zeros(reduced.shape, dtype=bool) for name in LAYER_INFO}
    messages = [
        "Educational CPU heuristics only; all layers require independent review and may leak or omit anatomy.",
        "Native HU is preserved. Surfaces use a reduced sampling grid and are not source-slice evidence.",
        "Surfaces are display-smoothed with bounded vertex motion; do not use them for diagnostic size measurements.",
        "Vessel candidates are dense intrapulmonary structures, not a complete vascular tree or artery/vein labels.",
        "Reviewed labelmap import is not supported in this version. Annotations are unverified spheres only.",
    ]
    if min(reduced.shape) < 3:
        messages.append("Candidate segmentation omitted: insufficient grid coverage.")
        return masks, label_affine, stride, messages
    body = np.zeros(reduced.shape, dtype=bool)
    area = float(np.linalg.norm(label_affine[:3, 0]) * np.linalg.norm(label_affine[:3, 1]))
    voxel_size = abs(float(np.linalg.det(label_affine[:3, :3])))
    plane_spacing = np.linalg.norm(label_affine[:3, :2], axis=0)[::-1]
    opening = physical_disk(plane_spacing, max(1.5, float(plane_spacing.min())))
    closing = physical_disk(plane_spacing, 1.5)
    for k, plane in enumerate(reduced):
        tissue = ndi.binary_opening(plane > -450, iterations=1)
        body[k] = ndi.binary_fill_holes(components(tissue, minimum=16, keep=1))
        interior = body[k] & (plane < -450)
        # Opening breaks narrow central-airway connections before selecting lung pockets.
        lung_air = ndi.binary_opening(interior, structure=opening)
        lung_air = components(lung_air, minimum=max(12, int(200 / area)), keep=2)
        envelope = ndi.binary_fill_holes(lung_air)
        masks["lungs"][k] = ndi.binary_closing(envelope, structure=closing) & body[k]
    masks["airways"], airway_messages = airway_candidates(reduced, body, label_affine)
    messages.extend(airway_messages)
    masks["lungs"] &= ~masks["airways"]
    masks["lungs"] = components(masks["lungs"], minimum=max(24, int(1000 / voxel_size)), keep=2)
    inner_lung = ndi.binary_erosion(masks["lungs"], iterations=2)
    masks["vessels"] = components(
        inner_lung & (reduced > -300) & (reduced < 300),
        minimum=max(4, int(30 / voxel_size)), keep=128,
    )
    masks["bones"] = components(body & (reduced > 250), minimum=max(8, int(100 / voxel_size)), keep=128)
    for name, mask in masks.items():
        if not mask.any():
            messages.append(f"{name}: no supported candidate component; layer omitted.")
    return masks, label_affine, stride, messages


def mesh_for_mask(mask, affine_lps, native_shape=None, stride=None, smooth=True):
    if not mask.any() or min(mask.shape) < 2:
        return None
    padded = np.pad(mask.astype(np.uint8), 1)
    # Retry with a coarser extraction step rather than creating enormous JSON arrays.
    for step in (1, 2, 3, 4):
        try:
            vertices, faces, _, _ = marching_cubes(padded, 0.5, step_size=step, allow_degenerate=False)
        except (ValueError, RuntimeError):
            return None
        if len(faces) <= 180_000:
            break
    if len(faces) > 180_000:
        return None
    ijk = (vertices - 1)[:, ::-1]
    if native_shape is not None:
        stride = np.asarray(stride)[::-1]
        ijk = np.clip(ijk, -0.5 / stride, (np.asarray(native_shape)[::-1] - 0.5) / stride)
    positions = ijk @ affine_lps[:3, :3].T + affine_lps[:3, 3]
    if smooth:
        # One small Laplacian pass affects display vertices only, never HU or labels.
        original = positions.copy()
        neighbors = np.zeros_like(positions)
        degree = np.zeros(len(positions), dtype=np.int32)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            np.add.at(neighbors, faces[:, a], original[faces[:, b]])
            np.add.at(neighbors, faces[:, b], original[faces[:, a]])
            np.add.at(degree, faces[:, a], 1)
            np.add.at(degree, faces[:, b], 1)
        displacement = 0.3 * (neighbors / np.maximum(degree[:, None], 1) - original)
        limit = min(0.75, 0.35 * np.linalg.svd(affine_lps[:3, :3], compute_uv=False).min())
        length = np.linalg.norm(displacement, axis=1)
        displacement *= np.minimum(1, limit / np.maximum(length, 1e-12))[:, None]
        positions += displacement
    positions[:, :2] *= -1
    # Reversing k,j,i to i,j,k changes handedness; account for the affine determinant.
    if np.linalg.det(affine_lps[:3, :3]) > 0:
        faces = faces[:, ::-1]
    return {"positions": np.round(positions, 4).ravel().tolist(), "indices": faces.ravel().tolist()}
