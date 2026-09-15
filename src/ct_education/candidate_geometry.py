"""Bounded native-HU candidate extraction; no sphere prior or invented closure."""

import numpy as np
from scipy import ndimage
from skimage.measure import marching_cubes


def extract_candidate(volume, affine_ras, position_ras, *, half_extent_mm=12,
                      threshold_hu=-500, thresholds=(-600, -500, -400, -300)):
    affine = np.asarray(affine_ras, dtype=float)
    position = np.asarray(position_ras, dtype=float)
    if (affine.shape != (4, 4) or position.shape != (3,) or not np.isfinite(affine).all()
            or not np.isfinite(position).all() or not 4 <= half_extent_mm <= 30
            or not -900 <= threshold_hu <= 300 or threshold_hu not in thresholds
            or not thresholds or not all(-900 <= t <= 300 for t in thresholds)):
        raise ValueError('E_CANDIDATE_OPTIONS')
    inverse = np.linalg.inv(affine)
    ijk = (inverse @ np.r_[position, 1])[:3]
    seed_global = np.floor(ijk + 0.5).astype(int)
    shape = np.asarray(volume.shape)[::-1]
    if (seed_global < 0).any() or (seed_global >= shape).any():
        raise ValueError('E_CANDIDATE_SEED')
    spans = np.ceil(half_extent_mm * np.linalg.norm(inverse[:3, :3], axis=1)).astype(int)
    low = np.maximum(0, seed_global - spans)
    high = np.minimum(shape, seed_global + spans + 1)
    roi = volume[low[2]:high[2], low[1]:high[1], low[0]:high[0]].copy()
    if not np.isfinite(roi).all():
        raise ValueError('E_CANDIDATE_HU')
    seed = tuple((seed_global - low)[::-1])
    masks, trials = {}, []
    voxel_mm3 = abs(np.linalg.det(affine[:3, :3]))
    for threshold in thresholds:
        labels, _ = ndimage.label(roi >= threshold, np.ones((3, 3, 3), dtype=bool))
        component = int(labels[seed])
        mask = labels == component if component else np.zeros(roi.shape, bool)
        coordinates = np.argwhere(mask)
        touches = bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()
                       or mask[:, :, 0].any() or mask[:, :, -1].any())
        if len(coordinates):
            ras = coordinates[:, ::-1] @ affine[:3, :3].T
            extent = np.ptp(ras, axis=0) + np.linalg.norm(affine[:3, :3], axis=1)
            elongation = float(extent.max() / max(extent.min(), 1e-6))
        else:
            extent, elongation = np.zeros(3), 0.0
        masks[threshold] = mask
        trials.append(dict(threshold_hu=threshold, voxels=int(mask.sum()), volume_mm3=float(mask.sum() * voxel_mm3),
                           extent_ras_mm=extent.tolist(), touches_roi_edge=touches, elongation=elongation))
    chosen = trials[list(thresholds).index(threshold_hu)]
    mask = masks[threshold_hu]
    overlap = []
    for threshold in thresholds:
        union = (mask | masks[threshold]).sum()
        overlap.append(float((mask & masks[threshold]).sum() / union) if union else 0.0)
    reasons = []
    if chosen['voxels'] < 4:
        reasons.append('insufficient_seed_connected_evidence')
    if chosen['touches_roi_edge']:
        reasons.append('selected_component_reaches_roi_edge')
    if not 1 <= chosen['volume_mm3'] <= 1500:
        reasons.append('component_volume_outside_display_gate')
    if chosen['elongation'] > 4:
        reasons.append('elongated_component_possible_vessel')
    basic_reasons = list(reasons)
    lower = [t for t in trials if t['threshold_hu'] < threshold_hu]
    if any(t['touches_roi_edge'] for t in lower):
        reasons.append('lower_threshold_connects_to_roi_edge')
    if sum(value >= 0.45 for value in overlap) < min(3, len(thresholds)):
        reasons.append('threshold_sensitive_boundary')
    density_mesh = None
    if not basic_reasons:
        # Outside the selected component, retain below-threshold HU, not a filled cap.
        field = np.where(mask, roi, np.minimum(roi, threshold_hu - 1)).astype(np.float32)
        vertices, faces, _, _ = marching_cubes(field, level=threshold_hu, allow_degenerate=False)
        ras = (vertices[:, ::-1] + low) @ affine[:3, :3].T + affine[:3, 3]
        density_mesh = dict(positions=ras.ravel().tolist(), indices=faces.ravel().tolist())
    # Displaying a measured level set does not promote a failed boundary assessment.
    mesh = density_mesh if not reasons else None
    roi_affine = affine.copy()
    roi_affine[:3, 3] = (affine @ np.r_[low, 1])[:3]
    report = dict(status='approximate_surface' if mesh else 'localized_region_boundary_unverified',
                  reasons=reasons, selected_threshold_hu=threshold_hu, thresholds=trials,
                  jaccard_to_selected=overlap, seed_hu=float(roi[seed]), seed_ras=position.tolist(),
                  roi_low_ijk=low.tolist(), roi_high_ijk=high.tolist(), roi_affine_ras=roi_affine.tolist(),
                  half_extent_mm=half_extent_mm,
                  method='native HU threshold; seed-connected 26-neighborhood; no morphology or smoothing',
                  uncertainty='Approximate threshold surface, not a clinical boundary or vessel separation.')
    density_display = dict(representation_type='exploratory_isodensity', threshold_hu=threshold_hu,
                           available=density_mesh is not None, verified_nodule_boundary=False,
                           unavailable_reasons=basic_reasons, boundary_warnings=list(reasons),
                           meaning='Native-HU seed-connected level set, not an isolated or verified nodule boundary.')
    return dict(report=report, mesh=mesh, density_mesh=density_mesh, density_display=density_display,
                mask=mask, masks=masks, hu=roi, affine_ras=roi_affine)
