# Product Requirements

## Goal and Scope

The planned CT Education Skill helps learners explore chest anatomy in a local interactive 3D viewer and check every spatial selection against original slices. Current status is scaffold only; none of the application behavior below exists yet.

It is not intended for diagnosis, clinical advice, or treatment planning. Algorithmic outputs are candidate layers, not confirmed anatomy. Reviewed external labels are not automatically ground truth. Noncontrast scans do not justify promises of complete vasculature or reliable artery-vein separation.

## Planned Experience

- Toggle lung, airway, and vessel candidate layers, with method, review status, and uncertainty visible.
- Move axial, sagittal, coronal, or oblique cut planes without baked static shadows.
- Select a 3D location and see corresponding native source slices, 0-based voxel indices, and physical coordinates. Distinguish interpolated renderings from original slice proof.
- Follow a deterministic local `tour.json` with source-coordinate stops, camera targets, and layer visibility. Tour text teaches anatomy, not clinical interpretation.

## CPU Baseline

The v1 baseline will use native Hounsfield Units (HU), thresholding, chest/body and lung masks, connected components, and seeded region growing. Vessel-like regions remain exploratory candidates constrained by chest/lung masks, not a complete vascular tree. Missing branches, leaks, and ambiguous regions must remain visible limitations; warning heuristics cannot detect every error.

Import of externally reviewed labelmaps is planned, subject to grid alignment and provenance checks. No high-quality learned segmentation is promised without an explicitly supplied, licensed, and evaluated model. Heuristic scores must not appear as calibrated probabilities.

## Privacy and Local Operation

DICOM input is externally supplied and read-only to the tool. The output workspace is external. Repository, input root, and workspace must be pairwise disjoint after real-path resolution, including symlinks and missing leaves resolved through existing ancestors. Recheck before writes and reject output symlinks that escape the workspace. The [RFC](rfc.md) defines the planned enforcement contract.

No medical assets, identifying case facts, or private derivatives belong in the repository, public frontend assets, docs, examples, logs, or CI. All synthetic fixtures are generated at test time outside the repository. Local logs use error codes and counts, not filenames, source paths, or header dumps.

The planned server binds to `127.0.0.1`; v1 has no remote publication, tunnel, or non-loopback binding. It serves only explicitly allowed external workspace assets, never the input DICOM root or repository tree. The frontend contains generic code only, with no telemetry, CDN dependencies, or cloud tour service.

## Phased Acceptance

| Phase | Deliverable and Exit Criteria |
| --- | --- |
| Scaffold, current | English docs, one skill, MIT license, offline hygiene tests and CI; no application claims. |
| MVP, planned | Fail-closed paths and native geometry, CPU candidates, reviewed-label import, linked slices/3D, local guided tour. Selections reproduce known synthetic source coordinates; no study is embedded in app assets. |
| QA, planned | Synthetic HU/oblique geometry roundtrips, independent series, path and symlink rejection, label import checks, CPU failure cases, and UI evidence. Separately authorized real-study review stays local and private. |
| Video, stretch | Optional downstream Blender and `render-video`; reproduce tour stops and preserve uncertainty labels. No dependency on Blender for MVP or authoritative data. |

Correct source linkage and honest candidate labeling take priority over mesh appearance. Performance and segmentation quality targets require later measurements; this scaffold claims neither.
