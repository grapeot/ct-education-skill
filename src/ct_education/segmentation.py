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


def components(mask, minimum=1, keep=None):
    labels, count = ndi.label(mask)
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


def segment(volume, affine):
    spacing = np.linalg.norm(affine[:3, :3], axis=0)[::-1]
    stride = np.maximum(1, np.maximum(np.ceil(np.asarray(volume.shape) / 192), np.floor(1.5 / spacing))).astype(int)
    reduced = np.asarray(volume[::stride[0], ::stride[1], ::stride[2]], dtype=np.float32)
    label_affine = affine @ np.diag([*stride[::-1], 1])
    masks = {name: np.zeros(reduced.shape, dtype=bool) for name in LAYER_INFO}
    messages = [
        "Educational CPU heuristics only; all layers require independent review and may leak or omit anatomy.",
        "Native HU is preserved. Surfaces use a reduced sampling grid and are not source-slice evidence.",
        "Vessel candidates are dense intrapulmonary structures, not a complete vascular tree or artery/vein labels.",
        "Reviewed labelmap import is not supported in this version. Annotations are unverified spheres only.",
    ]
    if min(reduced.shape) < 3:
        messages.append("Candidate segmentation omitted: insufficient grid coverage.")
        return masks, label_affine, stride, messages
    body = np.zeros(reduced.shape, dtype=bool)
    small_air = np.zeros(reduced.shape, dtype=bool)
    area = float(np.linalg.norm(label_affine[:3, 0]) * np.linalg.norm(label_affine[:3, 1]))
    voxel_size = abs(float(np.linalg.det(label_affine[:3, :3])))
    for k, plane in enumerate(reduced):
        tissue = ndi.binary_opening(plane > -450, iterations=1)
        body[k] = ndi.binary_fill_holes(components(tissue, minimum=16, keep=1))
        interior = body[k] & (plane < -450)
        # Opening breaks narrow central-airway connections before selecting lung pockets.
        lung_air = ndi.binary_opening(interior)
        lung_air = components(lung_air, minimum=max(12, int(200 / area)), keep=2)
        masks["lungs"][k] = ndi.binary_fill_holes(lung_air)
        low_labels, count = ndi.label(body[k] & (plane < -850))
        if count:
            sizes = np.bincount(low_labels.ravel()) * area
            coords = np.argwhere(body[k])
            if coords.size:
                lo, hi = coords.min(axis=0), coords.max(axis=0)
                center = (lo + hi) / 2
                for obj_index, region in enumerate(ndi.find_objects(low_labels), 1):
                    if region is None or not 5 <= sizes[obj_index] <= 250:
                        continue
                    midpoint = np.array([(s.start + s.stop - 1) / 2 for s in region])
                    if np.all(np.abs(midpoint - center) <= (hi - lo) * np.array([0.3, 0.2])):
                        small_air[k][low_labels == obj_index] = True
    superior_order = range(len(reduced) - 1, -1, -1) if label_affine[2, 2] > 0 else range(len(reduced))
    seed = np.zeros_like(small_air)
    for rank, k in enumerate(superior_order):
        if rank >= max(1, len(reduced) // 3):
            break
        if small_air[k].any():
            candidate = components(small_air[k], keep=1)
            seed[k] = candidate
            break
    if seed.any():
        masks["airways"] = ndi.binary_propagation(seed, mask=small_air)
    masks["lungs"] &= ~masks["airways"]
    masks["lungs"] = components(masks["lungs"], minimum=max(24, int(1000 / voxel_size)), keep=2)
    inner_lung = ndi.binary_erosion(masks["lungs"], iterations=2)
    masks["vessels"] = components(
        inner_lung & (reduced > -300) & (reduced < 300),
        minimum=max(4, int(30 / voxel_size)), keep=128,
    )
    masks["bones"] = components(body & (reduced > 250), minimum=max(8, int(100 / voxel_size)), keep=128)
    masks["airways"] = components(masks["airways"], minimum=max(4, int(20 / voxel_size)), keep=1)
    for name, mask in masks.items():
        if not mask.any():
            messages.append(f"{name}: no supported candidate component; layer omitted.")
    return masks, label_affine, stride, messages


def mesh_for_mask(mask, affine_lps, native_shape=None, stride=None):
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
    positions[:, :2] *= -1
    # Reversing k,j,i to i,j,k changes handedness; account for the affine determinant.
    if np.linalg.det(affine_lps[:3, :3]) > 0:
        faces = faces[:, ::-1]
    return {"positions": np.round(positions, 4).ravel().tolist(), "indices": faces.ravel().tolist()}
