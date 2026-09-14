# Product Requirements

## Goal

Provide a local educational tool and coding agent skill that reads chest CT, extracts limited CPU heuristic candidates, and links interactive 3D surfaces to native-grid slice views. **v0.1.0 backend, frontend, and video export are implemented and usable.** Correctness and source linkage take priority over cosmetic rendering; implementation completion does not establish segmentation quality or clinical validity.

## Implemented Baseline

- DICOM ingestion: External read-only folders containing loose files and ZIP packages, or a single ZIP, read without extraction. Frames with matching `SeriesInstanceUID` can span packages; different series remain separate. Supports consistent single-frame `CTImageStorage`, `MONOCHROME2`, HU rescaling, and near-axial uniform grids with supported tilted displacement. Rejects scouts, enhanced/multiframe objects, duplicate SOP frames/positions, and inconsistent or nonuniform stacks. Archive path, size, and symlink checks apply per ZIP; ZIP-inside-ZIP recursion is unsupported.
- Series selection: `inspect` reports numbers, counts, support status, reason codes, and skipped files. `build` defaults to the supported series with the most frames or accepts a unique `--series-number`. This is not a suitability assessment and never combines independent series.
- CPU segmentation: Body envelopes, thresholds, and seeded air propagation attempt lung, airway, dense intrapulmonary, and bone candidate layers. Airway growth uses 26-connectivity between accepted pockets, with superior seeding, physical pocket constraints, and bounded fallback to conservative or empty results. Spacing-aware morphology supports lung envelopes and bulk-air rejection. Branch identity/completeness remain unverified; omitted candidates carry warnings.
- Label grid: `labels.npy` is a reduced-grid uint8 bitfield, with values `lungs=1`, `airways=2`, `vessels=4`, `bones=8`. `labels-grid.json` records its own stride and affine.
- Source and surfaces: `volume.npy` preserves native-grid float32 HU; disposable `meshes/<layer-id>.json` contains flat RAS positions and triangle indices. A bounded display-only smoothing pass leaves HU and labels unchanged. Reduced-grid surfaces are not source-image evidence or diagnostic size measurements.
- External annotations: `--annotations` accepts an external JSON array of positions and radii. IDs and free text are replaced with generic text. These are unverified spheres, not segmented lesions or automatically detected findings.
- Video export: `render-video` captures the local viewer's full viewport, including controls and educational warnings, using headless Playwright Chromium and ffmpeg H.264 MP4 encoding. A timed orbit/tour and annotation-free source-slice sweep are implemented. Output is a new private MP4 inside the external workspace, with no overwrite. See [architecture](rfc.md#video-rendering) for transaction and option details.

## Runtime API

The server binds only to `127.0.0.1` and serves generic frontend assets plus these GET routes:

| Route | Result |
| --- | --- |
| `/api/manifest` | Versioned geometry, candidate layers, annotations, warnings, source summary, and embedded tour. |
| `/api/mesh/<layer-id>` | Flat RAS coordinates and triangle indices for a listed layer. |
| `/api/slice?axis=axial&index=0&wc=-600&ww=1500` | Windowed 8-bit PNG with `X-Slice-Index`; axis also accepts `coronal` or `sagittal`. `wc` and `ww` are optional with these defaults. |
| `/api/voxel?i=0&j=0&k=0` | Numeric `hu`, `lps`, and `ras` for an in-bounds native voxel. |

Indices in the examples illustrate syntax only. Raw volumes, labels, source DICOM, private provenance, and rendered MP4s have no serving route. The video browser separately allows only its exact loopback origin's GET/HEAD requests and blocks WebSockets and service workers; this is not an OS-wide network isolation claim.

## Viewer Interactions

- Three.js orbit, pan, and zoom with dynamic lighting and no baked shadows.
- Independent candidate layer toggles and opacity controls.
- Axial, coronal, and sagittal source-grid slice controls with windowing and voxel selection. Axial PNGs represent windowed acquired frames; other axes are cross-sections, not independently acquired images or world-axis reformats for oblique data.
- Coronal/sagittal 2D presentation uses physical aspect ratios and superior-up rows with inverse click mapping; backend PNGs remain unchanged. Slice scrolling moves an existing selection along that axis, drops stale HU, and refetches it. Crosshairs appear only on the selected slice.
- 3D selection linked to the nearest source voxel, HU, 0-based `[i,j,k]`, and physical LPS/RAS coordinates. Out-of-grid selections are rejected rather than clamped.
- RAS x/y/z clipping with uncapped-cut warnings. Cut openings are rendering boundaries, not anatomy.
- A local tour with source-coordinate targets and candidate focus. The frontend expands a minimal manifest tour with available-layer and source-slice stops without duplicating a sufficiently complete tour. Interactive transitions depend on the current view; the video renderer separately supplies explicit frame times.
- The optional 3D native-slice plane defaults off for overview/anatomy. Anatomy tour cameras fit actual requested layer bounds, distinct from candidate focus. Mobile panels collapse while the 2D source panel remains available.

Responsive controls are implemented. The coordinating maintainer verified desktop and mobile browser use with no console errors, including selection, clipping, and candidate focus, as well as successful video generation. These bounded checks do not establish high-fidelity masks or comprehensive cross-browser coverage.

## Limits and Non-Goals

Education and technical exploration only, not diagnosis, clinical advice, or treatment planning. No clinically validated viewer or trained segmentation model is provided. Candidate masks can leak, omit structures, and lose small branches through downsampling. Dense intrapulmonary candidates can contain nonvascular tissue; bone candidates can contain calcifications. No complete vasculature, artery-vein classification, or calibrated probabilities are promised.

Video export via `render-video` is implemented. Reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported. Tour data is embedded in `manifest.json`, not a separate `tour.json`. The [RFC](rfc.md) describes the implementation; current source and CLI help define shipped interfaces.

## Privacy and Paths

Repository, input, and workspace must be pairwise disjoint after real-path resolution, including equality and ancestor relationships. For a build, the workspace parent must exist but the target must not. Each build iteration uses a fresh external workspace. `manifest.json` is published last as the completion marker; incomplete output must not be served. Video rendering uses a completed workspace and writes a new MP4 inside it.

All runtime assets and case facts remain private and external, including sanitized derivatives. No raw patient data, derivatives, identifiers, private paths, or case facts belong in public repositories/history, assets, docs, PRs, issues, CI, or logs. Default to no uploads. GPT review requires explicit per-case user approval of material, purpose, and destination; build/test/release authorization is not upload consent. Agents cannot infer or self-grant it, and must stop before transmission if its scope is unspecified. This exception approves neither other providers nor public disclosure; the application has no upload route. See [privacy rules](../AGENTS.md#privacy-gate).

Synthetic fixtures are generated outside the repository. `provenance.json` stores private source mappings and is never served. Host/Origin guards and no-store headers reduce exposure but are not authentication or full anonymization. No public hosting, tunnels, runtime CDN, telemetry, or cloud tour service is part of v0.1.

## Acceptance and Backlog

- Implemented baseline: `inspect`, `build`, `serve`, `render-video`, geometry-preserving HU, reduced-grid candidates, local viewer, and private publication. All 69 Python tests with encoder smoke and 32 frontend unit tests passed; details are in [test status](test.md).
- Verified use: The coordinating maintainer reports successful authorized private generation, bounded desktop/mobile browser QA, and video generation. Mask quality remains a limitation, not a certified outcome. Each future input still needs task-specific review.
- Deferred: Reviewed labelmap import with grid/provenance validation and oblique viewing extensions. Any future learned model needs explicit supply, licensing, and evaluation; it is not a promised v0.1 capability.

Missing labels and missing warnings are not evidence of normal anatomy. Performance and quality claims require measurements, not inference from a successful build.
