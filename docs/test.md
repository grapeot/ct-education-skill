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

The first test command runs the pipeline suite; full discovery includes hygiene and video tests. The opt-in smoke command requires `ffmpeg` with `libx264` on `PATH`. The video unit tests use mocked browser/server orchestration; the smoke test uses real ffmpeg with synthetic frames, not a real browser. Playwright and Chromium are needed for actual video rendering, not these mocked tests; see [video setup](../README.md#optional-video-dependencies).

Tests use synthetic inputs generated in memory or external temporary storage, never real patient fixtures. Dependency installation may use the network; the synthetic tests use local computation and loopback HTTP. Default Python discovery skips the one opt-in smoke test; enable it with ffmpeg available to run the complete suite.

## Verification Status

- Verified on 2026-09-14 for iteration 2: **69 Python tests passed with the opt-in ffmpeg smoke enabled; 32 frontend unit tests passed**, both with zero skips. The documentation reviewer independently reran these suites.
- Python coverage comprises 32 pipeline tests, 9 repository hygiene tests, and 28 video tests. Without the smoke environment flag, the current suite has 68 passing tests and one skipped smoke test.
- The coordinating maintainer separately verified the production build, final desktop/mobile browser QA without console errors, and video export with successful ffprobe validation and full ffmpeg decoding. These generic functional outcomes do not certify segmentation or clinical quality.
- Required `master` check: `scaffold-hygiene`. Current CI runs default Python discovery, `npm test`, and the generic frontend build, but not the opt-in encoder smoke or Playwright browser installation. It does not deploy or upload artifacts. The current default Python suite skips one smoke test; the local opt-in run executes all 69.
- Maintainer-confirmed release status: [PR1](https://github.com/grapeot/ct-education-skill/pull/1) merged via normal squash after required GitHub CI passed. GLM privacy reviews for the scaffold and PR1 passed. PR2's privacy gate, submission, and remote CI result remain pending; PR1's pass is not a PR2 result.
- CLI help for all four subcommands and the Playwright browser-install command was checked against source. The earlier generic external annotation example was accepted on synthetic geometry with generic output IDs.
- The coordinating maintainer's final manual privacy gate remains required before PR submission; local test passes do not replace it. The documentation reviewer performs no Git mutations.

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

Coverage is bounded by the tested cases. It does not prove every schema edge case, arbitrary race resistance, all transfer syntaxes, or anatomical quality. Known dependency deprecation warnings during mesh tests are not failures; the reported full-suite rerun used `PYTHONWARNINGS=ignore`.

## Video Coverage

`tests/test_video.py` contains 28 tests for options, publication, and capture orchestration:

- Duration, fps, dimensions, and port bounds; output must be a new MP4 under the workspace, with traversal, symlink, and overwrite rejection.
- Missing ffmpeg/Playwright and browser-start failures, fixed CLI error codes, and sanitized output.
- Exact-origin browser route guards, external temporary profile/environment handling, and cleanup of server, browser, encoder, and staging on tested failure paths.
- Asset-readiness failures, explicit frame timing, tour selection, and source-slice sweep only when annotations are absent.
- Exclusive output publication, including a destination appearing during capture, and owner-only output mode.
- Opt-in real ffmpeg encoding of synthetic frames with mocked browser/server; checks MP4 structure and faststart placement of `moov` before `mdat`.

The encoder smoke is not full browser E2E. The separate maintainer-reported browser/video run supplies bounded integration evidence; it does not imply every browser or runtime failure path has been tested.

## Frontend Coverage

`frontend/tests/` contains 32 unit tests for client logic:

- Affine mapping and inversion, LPS/RAS conversion, finite manifest values, and mesh validation.
- Native PNG pixel mapping, slice extents/corners, physical orientation labels, and source-axis fallback for oblique geometry.
- Initial slice indices, selected voxel propagation, rejection of out-of-bounds selection, tour step bounds, visible layer selection, clipping state, and educational fallback titles.
- Four clipped-hit filtering tests: discarded mesh hits are skipped, unclipped slice/locator hits remain eligible, disabling clipping preserves the nearest hit, and all-discarded hits yield no selection.
- Two tour-expansion tests: minimal manifest tours gain local layer/source stops without duplicating a sufficiently complete tour.
- Five iteration-2 tests cover physical canvas aspect, superior-up display/click inversion, matching orientation labels, slice-selection updates that discard stale HU, and vascular fallback targets independent of annotation centers. These unit tests do not assert browser camera fitting or asynchronous HTTP refetch behavior.

These tests do not instantiate a browser renderer. They are not end-to-end evidence for camera movement, opacity rendering, WebGL picking, or desktop/mobile usability.

## Hygiene Review

Scaffold checks cover layout, the single root skill, fake configuration, license, CI declarations, ignore declarations, text inventory, and generic private markers. External synthetic probes exercise rejected names, binary content, symlinks, and private-text patterns. Ignore-declaration checks do not exercise Git's complete ignore engine. Environment, cache, and build directories can be excluded from scanning; inspect every proposed tracked or force-added file before each PR.

Automated scanning cannot recognize every identifying case fact. Keep all runtime inputs and derivatives outside the repository and public history. Public outcomes must remain generic even when local testing has separate authorization to use private inputs. Default to no uploads; any GPT review requires explicit per-case approval of material, purpose, and destination under [the privacy gate](../AGENTS.md#privacy-gate). General testing or release permission does not authorize transmission or public disclosure.

## Visual QA and Regressions

The coordinating maintainer completed final desktop/mobile browser QA without console errors and verified the final MP4 with ffprobe and full ffmpeg decoding. Earlier interaction checks included selection, clipping, and candidate focus. Successful rendering and decoding are not evidence of high-fidelity clinical masks or complete anatomy.

Future changes still need regression checks appropriate to their scope: desktop/mobile loading, layer visibility and opacity, uncapped cuts, source-linked picks/crosshairs, tour navigation, and candidate focus. Inspect native/reduced-grid alignment, orientation, leakage, and missing structures separately from UI functionality. For video, verify playable MP4 output, expected frame count, source linkage, and legible educational warnings. Check network/cache behavior locally.

Use synthetic scenes first and record exactly which interactions were exercised. Real-study evaluation requires separate authorization and external private storage. Keep images, screenshots, meshes, annotations, tours, and videos outside public PRs, CI, logs, and issue attachments. Record only generic outcomes publicly; a lack of observed defects is not proof of complete anatomy.
