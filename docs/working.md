# Working Status

## Current Status

The v0.1.0 backend Python package, `inspect`/`build`/`serve`/`render-video` CLI, and Three.js frontend are implemented and usable for local educational exploration. Video export uses Playwright Chromium and ffmpeg; optional `serve --video-file` now enables single-file streaming and click-only playback/download. Segmentation remains a limited CPU heuristic baseline, not validated models or high-fidelity clinical masks. Reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported.

Optional-media verification on 2026-09-14: **all 89 Python tests passed with the opt-in ffmpeg smoke enabled and all 42 frontend tests passed**, with zero skips, independently rerun by the documentation reviewer. The earlier ASCII hygiene finding is resolved. Maintainer-reported Chrome checks through authenticated private routing passed across desktop, portrait, and landscape viewports, including playback, seeking, download, close cleanup, focused-control Escape, and landscape footer fit. These are not iPhone Safari certification; see [test status](test.md).

The maintainer confirms [PR1](https://github.com/grapeot/ct-education-skill/pull/1) and [PR2](https://github.com/grapeot/ct-education-skill/pull/2) are merged. PR3 is not created; the current privacy gate, GLM review, submission, and remote CI outcomes remain pending. Previously recorded scaffold/PR1 privacy passes do not cover this iteration.

## Changelog

### 2026-09-14 (isolated visual preview)

- Added a preview-only style selector to audition five educational themes: Clinical, Atlas, Blueprint, Aurora, and Studio. Following user selection, Aurora is now the default and all anatomy layers start visible at their existing opacity. Old preview preferences do not override the selected default; production integration remains separate.
- Selection follow-up: 47 frontend tests and the build passed. Local Chrome confirmed Aurora startup, all anatomy layers enabled, and no page errors; desktop/mobile screenshots remain private.
- Switching styles preserves active slice position and viewer orientation without resetting state. Only an allowlisted theme preference is stored. The themes vary typography, control treatment, density, panel structure, and scene background without changing native CT pixels or anatomy colors.
- Verified 45 frontend tests and the production build. All 89 Python tests passed with encoder smoke using a harness that excludes the worktree Git pointer from file hygiene; the unmodified scanner flags that pointer as an unexpected file. No backend or test-scanner changes were made.
- Local Chrome checks covered desktop and mobile layouts, same-page state and pixel preservation, three source planes, six tours, native-video Escape and source cleanup, keyboard selection, denied storage, and reduced motion. Private screenshots remain outside the repository. These checks do not certify medical accuracy, iPhone Safari, or accessibility conformance.

### 2026-09-14 (final media validation and documentation)

- Recorded the maintainer's ASCII separator fix and capture-phase Escape handling for focused native video controls, preserving browser Escape behavior during native fullscreen. Independently reran all 89 Python tests with encoder smoke and 42 frontend tests; all passed with zero skips.
- Recorded maintainer-reported Chrome checks through authenticated private routing across desktop, portrait, and landscape viewports. Playback, 206 seeking, attachment download, no source before click, close cleanup/focus return, focused-control Escape, and landscape footer fit passed. No iPhone Safari certification is claimed.
- Corrected the PRD's stale MP4-serving prohibition and current test counts; synchronized all seven docs using a Cursor rough draft and source review. Runtime data remains external/private. Current privacy and GLM reviews remain pending; no Git commands or source edits by the documentation worker.

### 2026-09-14 (optional media and documentation)

- Added optional CLI selection of one workspace-relative MP4, generic video metadata, GET/HEAD streaming with single byte ranges, and attachment download. Video remains disabled by default; raw data, provenance, and unselected MP4s remain unserved.
- Added "Watch the tour" with click-only source attachment, modal playback/download, and pause/source removal on close. The UI uses neutral English copy and a high-tech visual style; browser acceptance was pending at this milestone. The capture server retains `video_file=None`, avoiding cyclic playback.
- Refreshed README, RFC, test status, working log, root skill, and contributor guidance from a Cursor rough draft with source/help review and surgical edits. Preserved external/private output boundaries and documented only generic authenticated-routing requirements.
- At this historical milestone, 88 of 89 Python tests passed with encoder smoke; the frontend ASCII hygiene failure was subsequently resolved. All then-current 39 frontend tests passed. No source edits or Git commands by the documentation worker; no runtime artifacts or case details recorded publicly.
- PR1 and PR2 were merged per maintainer confirmation. PR3 was not created; browser/private-route checks and the privacy gate were pending at this milestone. Current status is recorded above.

### 2026-09-14 (iteration 2 pipeline refinement and documentation)

- Refined airway growth with 26-connectivity, physical pocket constraints, conservative fallback, and spacing-aware morphology. Branch identity and completeness remain unverified.
- Added bounded display-only mesh smoothing, leaving native HU and labels unchanged by that pass. Preserved the native slice grid.
- Updated the seven public docs for physical-aspect/superior-up 2D presentation, inverse click mapping, off-slice/stale-HU handling, layer-fitted tours, and optional 3D source-plane visibility. Used a short Cursor draft followed by source review.
- Verified 69 Python tests with encoder smoke and 32 frontend tests. The maintainer reports successful build, final private browser QA, and video probe/full-decode checks. No case facts or runtime artifact metadata are recorded.
- At this historical milestone, PR1 had merged with required CI and prior privacy review passed; PR2 privacy review and submission were pending. Current release status is recorded above. No Git mutations by the documentation worker.

### 2026-09-14 (frontend slice/tour acceptance fixes)

- Frontend-only fixes for native-slice display aspect, off-plane selection readout, layer-bounded tour framing, mobile chrome overlap, and superior-up coronal/sagittal display. Canonical PNG endpoints and 3D texture UVs remain unflipped.
- Generic local checks: frontend unit tests and production build rerun. Authorized private browser recapture is recorded only as pass/fail in the caller-owned QA workspace. No case facts, identifiers, or geometry values are included here.
- These checks do not certify anatomy, segmentation, or clinical quality.
- Follow-up mobile layout fix: remove the horizontal flex basis from the vertically stacked focus card and reserve more height for the 3D stage. Browser acceptance is checked separately from unit tests.

### 2026-09-14 (frontend visual pass)

- Frontend-only iteration: quieter first-screen copy, optional 3D native-slice overlay defaulting off for overview/anatomy, and mobile control accordions collapsed while the 2D source panel stays available.
- Generic local checks: frontend unit tests and production build rerun. Authorized private browser recapture is recorded only as pass/fail in the caller-owned QA workspace. No case facts, identifiers, or geometry values are included here.
- These checks do not certify anatomy, segmentation, or clinical quality.

### 2026-09-14

- Initial scaffold: English requirements, architecture, contributor rules, one root skill, MIT license, external-only data boundaries, and offline hygiene CI. All 9 hygiene checks passed at that historical stage; this is separate from current runtime verification.
- Implemented DICOM inspection, native geometry/HU processing, CPU candidate masks, mesh generation, optional external annotations, manifest-last publication, and guarded loopback APIs.
- Implemented Three.js layer controls, native-grid slices, coordinate/voxel selection, clipping, candidate focus, and local tour navigation.
- Initial documentation milestone: refreshed six files from a Cursor rough draft and verified the then-current 18 backend and 21 frontend tests. Scanner integration and browser verification were still pending at that historical stage.
- Accepted the generic external annotation example on synthetic geometry and verified identifier replacement. Post-edit public hygiene scan returned zero findings; no real input was used for these checks.
- Added `render-video`: private browser profile, full-viewport capture, timed orbit/tour, annotation-free source-slice sweep, ffmpeg H.264 faststart MP4, and exclusive output publication.
- Extended input collection to loose DICOM plus ZIP packages, combining only matching series and rejecting duplicate SOP instances/positions. Added clipped-hit filtering and frontend tour expansion.
- Completed scanner integration and independently verified the full 61-test Python suite, including the opt-in synthetic ffmpeg smoke, and 27 frontend unit tests. The smoke uses real encoding but mocked browser/server orchestration.
- Coordinating maintainer verified authorized private generation, bounded desktop/mobile browser functionality without console errors, and video generation. Only generic results are recorded; no case facts, geometry, or runtime artifact details are included.
- Final seven-document refresh used a Cursor draft followed by source/help review. Corrected the default-local privacy policy to permit only explicit per-case user-approved GPT review of approved material, purpose, and destination. General build/test/release permission does not authorize uploads.
- At this pre-PR1 documentation milestone, the final privacy gate and remote PR/CI outcomes were still pending. Current release status is recorded above.
- No Git mutations were performed by the delegated documentation worker.

## Branch Protection

The coordinating maintainer confirms active protection on `master`: PRs required, zero required approvals, `enforce_admins: true`, required check `scaffold-hygiene`, and no force pushes or branch deletion. Current project PR/merge iteration is user-authorized and coordinated serially. Future mutations still require explicit authorization; the policy must not be bypassed or weakened.

## Development Checklist

- [x] Scaffold, documentation, license, single root skill, and CI definition.
- [x] Backend inspection, strict geometry/HU handling, CPU masks, and surface extraction.
- [x] External annotation schema and generic served text.
- [x] Guarded loopback server and native slice/voxel APIs.
- [x] Three.js viewer, candidate controls, clipping, and local tour.
- [x] Video export with private staging and no-overwrite MP4 publication.
- [x] CLI/user documentation and RFC updated for implemented v0.1.
- [x] Optional single-file video HTTP routes and click-only playback/download UI.
- [x] Independent current test run: all 89 Python tests with encoder smoke and all 42 frontend tests passed.
- [x] Frontend ASCII hygiene failure resolved and full Python suite rerun.
- [x] Maintainer-confirmed remote `master` protection.
- [x] Historical scanner integration and local full-suite verification.
- [x] Historical iteration-2 build, desktop/mobile browser QA, and video probe/full-decode verification.
- [x] PR1 merged via normal squash after required CI passed; scaffold/PR1 GLM privacy reviews passed.
- [x] PR2 merged per maintainer confirmation.
- [x] Maintainer-reported Chrome playback through authenticated private routing across desktop, portrait, and landscape viewports, including 206 seeking and close cleanup.
- [ ] Current privacy gate, GLM review, PR3 submission, and subsequent remote CI outcome; PR3 not created.
- [ ] Heuristic mask-quality review and refinement, with authorized evidence external.
- [ ] Deferred: reviewed labelmap import and oblique viewing extensions.

## Lessons Learned

- A visual selector must preserve the working surface, not just its state: repaint immediately after canvas resize, and avoid ancestor overflow rules that disable a sticky mobile selector.
- Native and reduced-grid affines differ: source HU and labels have distinct shapes, strides, and spatial transforms. Array indices alone do not establish alignment.
- Manifest-last publication matters: failure tests include partial destination publication without a completed manifest. An incomplete workspace is not a usable build; keep it separate from successful runs.
- Scaffold checks cannot establish runtime geometry or visual quality. Backend synthetic and frontend logic tests add bounded evidence, not anatomical or clinical validation.
