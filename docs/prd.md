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
- Cinematic export: `render-cinematic` implements the [36-second design](video_design.md) independently of browser capture. Shared source state preserves exact RAS-mm to Blender-meter mapping. Imagery before 28 seconds, including the 26-28 second parity proof, is unchanged. At 28-33 seconds, true 3D near-top branch context, a faint envelope, translucent source plane, and world-space locator stay on the left while native CT zooms on the right. The 33-36 second ending fades left context to airway candidates only, with bones hidden, a gentle arc/narrowing, and a 35.5-36 second hold. Right CT and its metric ruler stay fixed after 30 seconds; the left ruler disappears with its plane. Native HU is unchanged; no capillaries or nodules are fabricated, and locators are not segmented lesions.
- Optional playback: `serve --video-file demo.mp4 --rendered-video-file film.mp4` explicitly selects up to two existing regular MP4s by workspace-relative paths. Either flag can be used alone; both are disabled by default. Absolute paths, traversal, symlinks, and non-MP4 names are rejected. It does not enable directory or bulk output serving. The browser renderer's internal server leaves both selections unset to prevent cyclic playback.

## Runtime API

The server binds only to `127.0.0.1` and serves generic frontend assets plus these GET routes, with HEAD support:

| Route | Result |
| --- | --- |
| `/api/manifest` | Versioned geometry, candidate layers, annotations, warnings, source summary, and embedded tour. |
| `/api/mesh/<layer-id>` | Flat RAS coordinates and triangle indices for a listed layer. |
| `/api/slice?axis=axial&index=0&wc=-600&ww=1500` | Windowed 8-bit PNG with `X-Slice-Index`; axis also accepts `coronal` or `sagittal`. `wc` and `ww` are optional with these defaults. |
| `/api/voxel?i=0&j=0&k=0` | Numeric `hu`, `lps`, and `ras` for an in-bounds native voxel. |
| `/api/video-info` | `{"available":false}` by default; otherwise fixed top-level playback/download URLs plus `versions`. Demo is preferred, with rendered-only fallback. |
| `/api/video`, `/api/video/rendered` | Explicitly selected demo and film respectively, with GET/HEAD and single byte-range 206/416 responses; `?download=1` requests an attachment. Unconfigured routes return 404. |

Indices in the examples illustrate syntax only. Raw volumes, labels, source DICOM, private provenance, and unselected MP4s have no serving route. HTTP requests cannot select another video path. The capture browser separately allows only its exact loopback origin's GET/HEAD requests and blocks WebSockets and service workers; this is not an OS-wide network isolation claim.

## Viewer Interactions

- Three.js orbit, pan, and zoom with dynamic lighting and no baked shadows.
- Independent candidate layer toggles and opacity controls.
- Axial, coronal, and sagittal source-grid slice controls with windowing and voxel selection. Axial PNGs represent windowed acquired frames; other axes are cross-sections, not independently acquired images or world-axis reformats for oblique data.
- Coronal/sagittal 2D presentation uses physical aspect ratios and superior-up rows with inverse click mapping; backend PNGs remain unchanged. Slice scrolling moves an existing selection along that axis, drops stale HU, and refetches it. Crosshairs appear only on the selected slice.
- 3D selection linked to the nearest source voxel, HU, 0-based `[i,j,k]`, and physical LPS/RAS coordinates. Out-of-grid selections are rejected rather than clamped.
- RAS x/y/z clipping with uncapped-cut warnings. Cut openings are rendering boundaries, not anatomy.
- A local tour with source-coordinate targets and candidate focus. The frontend expands a minimal manifest tour with available-layer and source-slice stops without duplicating a sufficiently complete tour. Interactive transitions depend on the current view; the video renderer separately supplies explicit frame times.
- The optional 3D native-slice plane defaults off for overview/anatomy. Anatomy tour cameras fit actual requested layer bounds, distinct from candidate focus. Mobile panels collapse while the 2D source panel remains available.
- "Watch the tour" attaches the video source only after click. The version switch lives inside Guided walkthrough, not the main viewer. Switching pauses/resets/reloads the old source and updates direct-play/download links; paused playback stays paused, while switching from active playback can resume on the user gesture. Closing removes the source and links and restores focus. Escape closes the non-fullscreen modal from focused native controls; native fullscreen Escape remains browser-controlled. Legacy single-video metadata remains accepted for shipped compatibility.

Responsive controls and the Aurora default are implemented. Independent GPT QA in actual Chrome through authorized private HTTPS passed desktop, phone portrait, and landscape functional checks for both videos. Small mobile inline playback and some ruler-label offsets remain accepted P2 polish items, not launch blockers; fullscreen and the direct-play link are available. These bounded checks do not establish high-fidelity masks, continuous human aesthetic acceptance, iPhone Safari certification, or comprehensive cross-browser coverage; see [test status](test.md#visual-qa-and-regressions).

## Limits and Non-Goals

Education and technical exploration only, not diagnosis, clinical advice, or treatment planning. No clinically validated viewer or trained segmentation model is provided. Candidate masks can leak, omit structures, and lose small branches through downsampling. Dense intrapulmonary candidates can contain nonvascular tissue; bone candidates can contain calcifications. No complete vasculature, artery-vein classification, or calibrated probabilities are promised.

Both video renderers are implemented. Reviewed labelmap import, precise nodule-mask review, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported. Tour data is embedded in `manifest.json`, not a separate `tour.json`. The [RFC](rfc.md) describes the implementation; current source and CLI help define shipped interfaces.

## Privacy and Paths

Repository, input, and workspace must be pairwise disjoint after real-path resolution, including equality and ancestor relationships. For a build, the workspace parent must exist but the target must not. Each build iteration uses a fresh external workspace. `manifest.json` is published last as the completion marker; incomplete output must not be served. `render-video` writes a new MP4 inside the completed workspace. `render-cinematic` instead requires a new external run directory disjoint from that input workspace and repository, with an existing parent. All cinematic intermediates, logs, state, and the patient-derived packed `.blend` remain private. Only an explicitly approved copy of the final MP4 may be placed inside the viewer workspace for explicit selection; generation does not expose it automatically.

All runtime assets and case facts remain private and external, including sanitized derivatives. No raw patient data, derivatives, identifiers, private paths, or case facts belong in public repositories/history, assets, docs, PRs, issues, CI, or logs. Default to no uploads. GPT review requires explicit per-case user approval of material, purpose, and destination; build/test/release authorization is not upload consent. Agents cannot infer or self-grant it, and must stop before transmission if its scope is unspecified. This exception approves neither other providers nor public disclosure; the application has no upload route. See [privacy rules](../AGENTS.md#privacy-gate).

Synthetic fixtures are generated outside the repository. `provenance.json` stores private source mappings and is never served. Host/Origin guards and no-store headers reduce exposure but are not authentication or full anonymization. User-authorized private access uses one application server behind caller-managed authenticated routing and may include the selected MP4s; proxies must forward `Range` and preserve `Cache-Control: no-store`. No public hosting, public tunnels, static workspace serving, runtime CDN, telemetry, or cloud tour service is part of v0.1.

## Acceptance and Backlog

- Implemented baseline: all five CLI commands, geometry-preserving HU, reduced-grid candidates, local viewer, private output, and opt-in two-video playback/download. Independent reruns passed all 126 Python tests with encoder smoke and 53 frontend tests with zero skips; the production build remains a maintainer-reported pass. Details are in [test status](test.md).
- Verified use: the maintainer reports the revised 36-second, 1920x1080, 24 fps film completed with 864 frames and full validation/decode, without interpolation or audio, and is privately selected alongside the retained demo on one server. Earlier independent GPT Chrome QA passed scoped two-video functionality; it is not new aesthetic acceptance of the revised ending. Mask quality and continuous human aesthetic acceptance remain uncertified.
- Deferred: Reviewed labelmap import with grid/provenance validation and oblique viewing extensions. Any future learned model needs explicit supply, licensing, and evaluation; it is not a promised v0.1 capability.

Missing labels and missing warnings are not evidence of normal anatomy. Performance and quality claims require measurements, not inference from a successful build.
