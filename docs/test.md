# Tests and Verification

## Test Commands

Use the [installation instructions](../README.md#installation), including `uv venv` if needed and `uv pip install -e .`. From the repository root with the environment activated:

```bash
source .venv/bin/activate
python -B -m unittest discover -s tests -p test_pipeline.py -v
python -B -m unittest discover -s tests -v
CT_EDU_VIDEO_FFMPEG_SMOKE=1 python -B -m unittest discover -s tests -v
npm --prefix frontend test
npm --prefix frontend run build
```

The first test command runs the pipeline suite; full discovery includes hygiene and video tests. The opt-in smoke command requires `ffmpeg` with `libx264` on `PATH`. Browser-video unit tests use mocked browser/server orchestration; the smoke test uses real ffmpeg with synthetic frames, not a real browser. Playwright and Chromium are needed for actual `render-video` capture, not these mocked tests or `render-cinematic`; see [video setup](../README.md#optional-video-dependencies).

Tests use synthetic inputs generated in memory or external temporary storage, never real patient fixtures. Dependency installation may use the network; the synthetic tests use local computation and loopback HTTP. Default Python discovery skips the one opt-in smoke test; enable it with ffmpeg available to run the complete suite.

## Verification Status

- Independently rerun by the documentation reviewer on 2026-09-14 after the depth-view/ending revision: **all 126 Python tests passed with the opt-in ffmpeg smoke enabled; all 53 frontend tests passed**, with zero skips. The production build remains a prior maintainer-reported pass, not a build rerun in this documentation pass.
- Python coverage comprises 32 pipeline, 10 repository hygiene, 28 browser-video, 20 video HTTP, 9 two-video catalog, and 27 cinematic tests. Default discovery skips the one opt-in smoke test; the enabled run executes all 126.
- Prior iteration-2 verification passed 69 Python and 32 frontend tests. The coordinating maintainer then verified the production build, desktop/mobile browser QA without console errors, and video export with successful ffprobe validation and full ffmpeg decoding. Those results do not establish acceptance of the new playback UI or authenticated routing, and do not certify segmentation or clinical quality.
- Required `master` check: `scaffold-hygiene`. Current CI runs default Python discovery, `npm test`, and the generic frontend build, but not the opt-in encoder smoke or Playwright browser installation. It does not deploy or upload artifacts. No remote CI result for the pending implementation PR is claimed.
- Maintainer-confirmed release status: PR4 (Aurora) and PR5 (36-second design) are merged with privacy review and CI. The whole-implementation GLM privacy gate and subsequent commit/PR submission remain with the coordinating maintainer. No PR6 creation or CI result is claimed; earlier reviews do not replace the current gate.
- CLI help for all five subcommands was checked against current source. The earlier generic external annotation example was accepted on synthetic geometry with generic output IDs.
- This documentation pass changed only the eight owned Markdown files and independently reran the Python and frontend suites. All 10 scaffold/hygiene tests passed with no public-file hygiene findings. It performed no Git commands, source edits, renders, or browser QA. Current publication review remains with the coordinating maintainer; this documentation review used GPT only.

## Backend Coverage

`tests/test_pipeline.py` covers 32 synthetic cases:

- Physical slice sorting, oblique/tilted affine displacement, inverse coordinate roundtrips, and native HU preservation.
- Signed/unsigned pixels and per-slice rescale slope/intercept, plus rejection of invalid stack metadata, duplicate positions, and inconsistent grids.
- Supported-series selection, explicit selection ambiguity, loose DICOM plus ZIP scanning, and same-series frame combination across packages without extraction. Tests reject repeated SOP instances rather than deduplicating, check each archive's path/size/symlink rules, and exercise resource cleanup after a later archive fails.
- Real-path overlap and symlink-ancestor checks, no-follow local file access, no overwrite, and build failure behavior before and during publication.
- JPEG Lossless decoder plugin availability. This is a registration check, not a compressed-image roundtrip or universal transfer-syntax validation.
- Candidate masks on synthetic primitives, exclusion of synthetic table-like material, reduced-grid affine/stride, empty candidates, and surface bounds including oblique transforms.
- Eight iteration-2 tests cover branching airway recovery without native changes, large-pocket leakage rejection, diagonal connectivity through final filtering, bounded overgrowth, affine-directed superior seeding, rejection of fragmented bulk-lung seeds, anisotropic physical morphology, and bounded deterministic smoothing with labels unchanged.
- Annotation position/radius validation and replacement of supplied private-text markers with generic candidate text.
- Native slice extraction without backend flips, known voxel HU/coordinates, allowed mesh routes, and rejection of traversal or private-file routes.
- Loopback Host/Origin guards, no-store headers, and rejection of symlink-replaced assets.

Coverage is bounded by the tested cases. It does not prove every schema edge case, arbitrary race resistance, all transfer syntaxes, or anatomical quality. Known dependency deprecation warnings during mesh tests are not failures.

## Video Coverage

`tests/test_video.py` contains 28 tests for options, publication, and capture orchestration:

- Duration, fps, dimensions, and port bounds; output must be a new MP4 under the workspace, with traversal, symlink, and overwrite rejection.
- Missing ffmpeg/Playwright and browser-start failures, fixed CLI error codes, and sanitized output.
- Exact-origin browser route guards, external temporary profile/environment handling, and cleanup of server, browser, encoder, and staging on tested failure paths.
- Asset-readiness failures, explicit frame timing, tour selection, and source-slice sweep only when annotations are absent.
- Exclusive output publication, including a destination appearing during capture, and owner-only output mode.
- Opt-in real ffmpeg encoding of synthetic frames with mocked browser/server; checks MP4 structure and faststart placement of `moov` before `mdat`.

The encoder smoke is not full browser E2E. The separate maintainer-reported browser/video run supplies bounded integration evidence; it does not imply every browser or runtime failure path has been tested.

`tests/test_video_http.py` adds 20 synthetic cases for optional single-file serving: disabled-by-default behavior, generic metadata, inline/attachment GET and HEAD, bounded/open-ended/suffix ranges, 206/416 responses, and request guards. It covers startup path/type/symlink rejection, tested post-startup replacements, current file sizes, bounded reads, hidden-file exclusion, and CLI defaults/errors. These are loopback HTTP tests, not browser playback or authenticated-proxy validation.

`tests/test_video_catalog.py` adds 9 synthetic cases for both-disabled, demo-only, rendered-only, and both-enabled metadata/defaults; both fixed route/download names; GET/HEAD and 206/416 film ranges; shared startup rejection; replaced/missing film behavior without demo fallback; changed file sizes; route/query guards; and additive CLI flags with sanitized errors.

## Cinematic Coverage

`tests/test_cinematic.py` contains 27 synthetic unit tests. They cover native/cropped pixel-center mapping and read-only HU, asymmetric non-axial orientation, shear rejection, ruler selection, option/output boundaries, and CLI defaults/errors. Timeline checks cover all 864 frame states and shot boundaries, monotone Hermite orbit knots and shared velocities, a full unwrapped turn, distinct fast-slow-fast contrast, staged stack entry/restoration, steady sweep interiors and holds, proof continuity and the 26-28 second hold, local/closing holds, branch emphasis, serializable candidate crops, and framing state. Three added tests cover true depth-view state without image-parity claims, continuous monotone ending fade/narrowing with the 35.5-36 second hold, and unchanged right CT pixels/crop/ruler after 30 seconds. Ending assertions also check absent bones/plane/left ruler. These tests do not run Blender or certify rendered appearance.

The coordinating maintainer reports the revised authorized film completed at **36 seconds, 1920x1080, 24 fps, 864 Blender frames**, with full validation, MP4 probe, and full ffmpeg decode passed. Pre-28-second imagery is unchanged; the new final shots retain left 3D depth and isolate airway candidates while right CT stays fixed after 30 seconds. No temporal interpolation, audio, source-HU changes, or fabricated capillaries/nodules were introduced. The new private film is selected alongside the retained 30-second demo on one application server in the primary checkout. Earlier paired-image checks support near-perfect correlation in the unchanged face-on proof and distinct fast-slow-fast motion, not parity of the new tilted depth view. No case coordinates, image values, identifiers, paths, or exact study-derived metrics are published here; technical completion is not continuous human aesthetic certification.

## Frontend Coverage

`frontend/tests/` contains 53 unit tests for client logic:

- Affine mapping and inversion, LPS/RAS conversion, finite manifest values, and mesh validation.
- Native PNG pixel mapping, slice extents/corners, physical orientation labels, and source-axis fallback for oblique geometry.
- Initial slice indices, selected voxel propagation, rejection of out-of-bounds selection, tour step bounds, visible layer selection, clipping state, and educational fallback titles.
- Four clipped-hit filtering tests: discarded mesh hits are skipped, unclipped slice/locator hits remain eligible, disabling clipping preserves the nearest hit, and all-discarded hits yield no selection.
- Two tour-expansion tests: minimal manifest tours gain local layer/source stops without duplicating a sufficiently complete tour.
- Five iteration-2 tests cover physical canvas aspect, superior-up display/click inversion, matching orientation labels, slice-selection updates that discard stale HU, and vascular fallback targets independent of annotation centers. These unit tests do not assert browser camera fitting or asynchronous HTTP refetch behavior.
- Seven video logic tests cover valid same-origin metadata, unavailable/missing responses, rejected external/traversal paths, URL canonicalization, and click-only source state with close resetting that state. They do not exercise DOM pause/load calls, focus restoration, downloads, or real media playback.
- Three additional video logic tests cover Escape from focused video controls, preserving native fullscreen Escape, and ignoring unrelated keys or a closed modal. These bring video logic coverage to 10 tests; browser event delivery is checked separately.
- Six two-video tests extend that historical video coverage to 16: catalog/default selection and legacy metadata, invalid catalogs, exact per-version URLs, state switching, media pause/reset/load behavior, and modal buttons/descriptions/links using test doubles. Five theme tests cover the selected Aurora defaults and theme-state behavior. Actual browser links and real playback are checked separately in Chrome.

These tests do not instantiate a browser renderer. They are not end-to-end evidence for camera movement, opacity rendering, WebGL picking, or desktop/mobile usability.

## Hygiene Review

Scaffold checks cover layout, the single root skill, fake configuration, license, CI declarations, ignore declarations, text inventory, and generic private markers. External synthetic probes exercise rejected names, binary content, symlinks, and private-text patterns. Ignore-declaration checks do not exercise Git's complete ignore engine. Environment, cache, and build directories can be excluded from scanning; inspect every proposed tracked or force-added file before each PR.

Automated scanning cannot recognize every identifying case fact. Keep all runtime inputs and derivatives outside the repository and public history. Public outcomes must remain generic even when local testing has separate authorization to use private inputs. Default to no uploads; any GPT review requires explicit per-case approval of material, purpose, and destination under [the privacy gate](../AGENTS.md#privacy-gate). General testing or release permission does not authorize transmission or public disclosure.

## Visual QA and Regressions

For iteration 2, the coordinating maintainer completed desktop/mobile browser QA without console errors and verified the MP4 with ffprobe and full ffmpeg decoding. Earlier interaction checks included selection, clipping, and candidate focus. Successful rendering and decoding are not evidence of high-fidelity clinical masks or complete anatomy.

Independent GPT QA in actual Chrome through authorized caller-managed private HTTPS passed desktop, phone portrait, and landscape checks: both version controls, the retained 30-second demo and 36-second film durations, playback, seeking, matching direct-play/download links, attachment download, no MP4 request before click, close-time pause/source removal, and pause/reset behavior when the video changes. Prior checks also covered focus restoration, Escape from focused controls, and landscape footer fit. These are bounded functional checks, not iPhone Safari certification, comprehensive cross-browser coverage, clinical validation, or continuous human aesthetic acceptance. This documentation worker did not repeat browser QA.

Accepted non-blocking P2 polish remains: the mobile inline film is small, with native fullscreen and the direct-play link available; some ruler-label offsets need readability refinement. These are future polish items, not new launch gates. The renderer's validation record still marks continuous-playback motion review pending; the functional PASS does not silently promote that field to aesthetic acceptance.

Keep native fullscreen Escape behavior, backdrop dismissal, and unavailable-video fallback in future regressions. Caller-managed authenticated proxies must forward `Range` and preserve `Cache-Control: no-store`; retain deployment details privately.

Future changes still need regression checks appropriate to their scope: desktop/mobile loading, layer visibility and opacity, uncapped cuts, source-linked picks/crosshairs, tour navigation, and candidate focus. Inspect native/reduced-grid alignment, orientation, leakage, and missing structures separately from UI functionality. For video, verify playable MP4 output, expected frame count, source linkage, and legible educational warnings. Check network/cache behavior locally.

Use synthetic scenes first and record exactly which interactions were exercised. Real-study evaluation requires separate authorization and external private storage. Keep images, screenshots, meshes, annotations, tours, and videos outside public PRs, CI, logs, and issue attachments. Record only generic outcomes publicly; a lack of observed defects is not proof of complete anatomy.
