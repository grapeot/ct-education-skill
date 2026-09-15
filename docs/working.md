# Working Status

## Current Status

The backend, all five CLI commands, and Three.js frontend are implemented on the current branch. The combined implementation adds the 36-second offline Blender film and explicit demo/film selection inside Guided walkthrough, retaining the browser demonstration and Aurora default. Segmentation remains a limited CPU heuristic baseline, not validated models or high-fidelity clinical masks. Reviewed labelmap import, precise nodule-mask review, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported.

Current verification on 2026-09-14: the documentation reviewer independently reran **all 126 Python tests with ffmpeg smoke enabled and all 53 frontend tests**, with zero skips. This includes all 27 cinematic tests; the production build remains a prior maintainer-reported pass. Earlier independent GPT Chrome QA through authorized private HTTPS passed scoped desktop/phone/landscape two-video functionality, not continuous human aesthetic acceptance of the revised ending. See [test status](test.md) for scope and attribution.

The maintainer confirms PR4 (Aurora) and PR5 (36-second design) are merged with privacy review and CI. The user authorized film rendering and code publication after the design PR. The whole-implementation GLM privacy gate and subsequent commit/PR submission remain pending with the coordinating maintainer; no PR6 creation or remote CI result is claimed. The maintainer reports the new private film is selected alongside the retained 30-second demo on one application server in the primary checkout behind caller-managed authenticated routing. This documentation worker performs no source, Git, or server operations.

The revised film completed at 36 seconds, 1920x1080, 24 fps with 864 Blender frames and full validation/decode per maintainer confirmation, without interpolation or audio. Imagery before 28 seconds, including the 26-28 second parity proof, is unchanged. The 28-33 second left view retains true 3D branch context and a world-space locator while the right zooms native CT; the ending fades left context to airway candidates with gentle arc/narrowing and a 35.5-36 second hold. Right CT/ruler stay fixed after 30 seconds, and the left ruler disappears with its plane. Native HU is unchanged; no capillaries or nodules are invented. All outputs, including `.blend`, stay private. P2 mobile-inline/ruler-label polish remains non-blocking; clinical and continuous human aesthetic certification are not claimed.

## Changelog

### 2026-09-14 (3D depth and airway ending revision)

- Replaced the final flat left CT close-up with near-top 3D airway/vascular context, faint envelope, translucent source plane, and a world-space supplied-candidate ring. The right remains the native CT zoom; source HU and sampling are unchanged.
- Replaced the overview return with an airway-only ending: fade left plane/envelope/vascular context/locator over 33-33.6 seconds, keep bones hidden, narrow the field 10% through an approximately 21-degree camera arc, and hold at 35.5-36 seconds. Right CT and its metric ruler remain fixed after 30 seconds; remove the left ruler with its plane.
- Maintainer reports the revised external 36-second 1920x1080/24 fps film passed full validation/decode with 864 frames; pre-28-second imagery is unchanged. It is privately selected alongside the retained demo on the single application server. Technical completion is not continuous human aesthetic certification.
- Updated only the eight owned English public-safe documents from renderer/test source. Independently reran 126 Python tests including ffmpeg smoke and 27 cinematic tests, plus 53 frontend tests: all passed with zero skips. No source/Git/server changes or new render/browser QA by this worker. The whole-implementation GLM privacy gate and PR submission remain with the coordinating maintainer.

### 2026-09-14 (prior combined cinematic and two-video implementation)

- Implemented the approved 36-second schedule, staged stack entry, controlled branch emphasis, an unwrapped fast-slow-fast full turn, synchronized source sweeps, a stable face-on proof at 26-28 seconds, local detail at 30-33 seconds, and closing hold. Native HU, exact coordinate mapping, and source-pair/ruler geometry remain unchanged by display motion.
- Completed the authorized 1920x1080/24 fps film with 864 frames and full decode/probe checks. Private paired-image comparison supports near-perfect correspondence in the matched pose; distinct fast-slow-fast motion is supported by bounded numerical evidence. No case-derived measurements or assets are recorded publicly.
- Added explicit `--rendered-video-file` alongside `--video-file`, fixed demo/film metadata and GET/HEAD/Range/download routes, and click-only version switching in Guided walkthrough. Switching resets the old source and updates direct-play/download links without making a paused player autoplay. Legacy metadata remains supported for shipped compatibility.
- The cinematic output remains a new external directory disjoint from its input workspace and repository. Serving requires regular MP4s inside the viewer workspace, selected explicitly. Copy only the final film there after explicit approval; generation never exposes the run or intermediates automatically.
- Maintainer reports 123 Python tests, including 24 cinematic tests and ffmpeg smoke, and 53 frontend tests passed with zero skips, plus the production build. Independent GPT Chrome desktop/phone/landscape functional QA passed through authorized private HTTPS. P2 mobile-inline and ruler-label polish is accepted without blocking launch; no clinical or continuous human aesthetic certificate is claimed.
- Updated the eight public Markdown documents by reviewing the existing drafts against renderer/server/CLI/frontend source and help, using GPT only. The documentation pass reran all 10 scaffold/hygiene tests: passed with zero skips and no public-file hygiene findings. It did not repeat full-suite, render, or browser QA. PR4 and PR5 are merged; the new implementation PR remains with the coordinating maintainer.

### 2026-09-14 (historical isolated visual preview)

- Added a preview-only style selector to audition five educational themes: Clinical, Atlas, Blueprint, Aurora, and Studio. Following user selection, Aurora became the default and all anatomy layers started visible at their existing opacity. Old preview preferences did not override the selected default; production integration was separate at this milestone and later merged in PR4.
- Selection follow-up: 47 frontend tests and the build passed. Local Chrome confirmed Aurora startup, all anatomy layers enabled, and no page errors; desktop/mobile screenshots remain private.
- Switching styles preserves active slice position and viewer orientation without resetting state. Only an allowlisted theme preference is stored. The themes vary typography, control treatment, density, panel structure, and scene background without changing native CT pixels or anatomy colors.
- Verified 45 frontend tests and the production build. All 89 Python tests passed with encoder smoke using a harness that excluded the worktree Git pointer from file hygiene; the then-current scanner flagged that pointer as an unexpected file. No backend or test-scanner changes were made at that milestone; the current scanner handles linked-worktree metadata explicitly.
- Local Chrome checks covered desktop and mobile layouts, same-page state and pixel preservation, three source planes, six tours, native-video Escape and source cleanup, keyboard selection, denied storage, and reduced motion. Private screenshots remain outside the repository. These checks do not certify medical accuracy, iPhone Safari, or accessibility conformance.

### 2026-09-14 (historical 72-second Blender cut)

- Wrote the original source-first 72-second storyboard before implementation, with shared patient-space plane/image state, simultaneous millimeter references, and explicit candidate uncertainty. [video_design.md](video_design.md) now describes the implemented 36-second cut; this entry records historical proof, not current recommended settings.
- Added opt-in `render-cinematic`, separate from the unchanged browser `render-video`, with deterministic Blender scene generation, external state/textures/packed master scene, individually rendered PNGs, offline dual-panel composition, MP4 encoding and full-decode validation. No frontend, live bundle, server routes, deployment, or Git mutations.
- Implemented source-grid axial/coronal/sagittal plane mapping, superior-up non-axial rows, affine-derived crop spacing, plane-anchored projected left rulers and physically resized right rulers. Sheared in-plane grids fail closed rather than pretending to be orthographic matches. Native HU stays read-only; the body footprint is an unreviewed display mask, not source segmentation.
- Initial authorized external face-on and spatial still renders completed. The face-on image was visually inspected for orientation/framing; the first spatial frame exposed excessive lighting and framing/noise issues, which triggered a new version. A still is not motion acceptance. Full-film production acceptance was pending at this milestone.
- Verified Blender 5.1.2 locally. Its EEVEE engine identifier is `BLENDER_EEVEE`, not the earlier `BLENDER_EEVEE_NEXT`. Initial failed run retained externally; public CLI returned a fixed error code.
- Completed a 12-second proof and a versioned 72-second, 1280x720, 24 fps film cut with 1,728 individually rendered frames, no interpolation, and no audio. These are generic production settings, not study facts. A correction reused unchanged source renders and rerendered affected stack/branch/projection-transition frames; no previous run was overwritten.
- Verified every expected source-render index and dimensions, opened and verified composed PNGs, checked ffprobe frame count/rate/duration/resolution, and fully decoded the MP4. Reloaded the packed master scene successfully. Actual decoded-frame temporal differences confirm still holds, left-only orbit motion, both-panel sweeps and local zoom; this is not a substitute for continuous-playback aesthetic review.
- All 103 Python tests passed with the optional synthetic ffmpeg smoke enabled, including 14 new cinematic tests. Frontend tests were not rerun by this worker because no frontend files changed. CLI help was verified. Public hygiene tests passed; coordinating maintainer still owns the release privacy gate.
- The historical cut's stack framing and bright-background ruler labels were corrected after inspection. Branch emphasis was still too restrained, and representative planes entered together rather than individually. The current 36-second implementation addresses branch emphasis and staged entry; broader aesthetic acceptance remains separate.
- Face-on parity validation applies only to the exact settled pose, not frames merely approaching it. A too-early tolerance gate initially stopped composition after Blender finished; corrected finalization reused those renders rather than rerendering the entire film. `finish_cinematic` is a trusted-run Python helper, not an advertised CLI resume flag.

Current generic proof invocation, requiring supported Blender EEVEE and ffmpeg/ffprobe, replaces the historical command:

```bash
ct-edu render-cinematic --workspace /path/to/external/built-study --output /path/to/external/new-cinematic-run --blender /path/to/blender --start 24 --duration 4 --fps 24 --samples 16 --budget 600
```

The new output directory must not exist and must be disjoint from the input build and repository. Current defaults are `--start 0 --duration 36 --fps 24`, 1280x720, 16 samples, and a 600-second Blender subprocess limit. Explicit `--width 1920 --height 1080` selects delivery resolution. The historical 72-second duration and proof starting at 36 seconds are invalid under the current timeline. Runtime outputs are not automatically exposed by the viewer.

### 2026-09-14 (historical single-video validation and documentation)

- Recorded the maintainer's ASCII separator fix and capture-phase Escape handling for focused native video controls, preserving browser Escape behavior during native fullscreen. Independently reran all 89 Python tests with encoder smoke and 42 frontend tests; all passed with zero skips.
- Recorded maintainer-reported Chrome checks through authenticated private routing across desktop, portrait, and landscape viewports. Playback, 206 seeking, attachment download, no source before click, close cleanup/focus return, focused-control Escape, and landscape footer fit passed. No iPhone Safari certification is claimed.
- Corrected the PRD's then-stale MP4-serving prohibition and test counts; synchronized all seven docs using a Cursor rough draft and source review. Runtime data remained external/private. Privacy and GLM reviews were pending at that historical milestone; no Git commands or source edits by the documentation worker.

### 2026-09-14 (historical optional media and documentation)

- Added optional CLI selection of one workspace-relative MP4, generic video metadata, GET/HEAD streaming with single byte ranges, and attachment download. Video remains disabled by default; raw data, provenance, and unselected MP4s remain unserved.
- Added "Watch the tour" with click-only source attachment, modal playback/download, and pause/source removal on close. The UI uses neutral English copy and a high-tech visual style; browser acceptance was pending at this milestone. The capture server retains `video_file=None`, avoiding cyclic playback.
- Refreshed README, RFC, test status, working log, root skill, and contributor guidance from a Cursor rough draft with source/help review and surgical edits. Preserved external/private output boundaries and documented only generic authenticated-routing requirements.
- At this historical milestone, 88 of 89 Python tests passed with encoder smoke; the frontend ASCII hygiene failure was subsequently resolved. All then-current 39 frontend tests passed. No source edits or Git commands by the documentation worker; no runtime artifacts or case details recorded publicly.
- At this historical milestone, PR1 and PR2 were merged per maintainer confirmation; the next optional-media submission, browser/private-route checks, and privacy gate were still pending. Current status is recorded above.

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
- [x] Optional two-video HTTP routes and click-only playback/download UI, preserving legacy metadata.
- [x] Current independent rerun: all 126 Python tests with encoder smoke, including 27 cinematic tests, and all 53 frontend tests passed; prior production build passed per maintainer.
- [x] Frontend ASCII hygiene failure resolved and full Python suite rerun.
- [x] Maintainer-confirmed remote `master` protection.
- [x] Historical scanner integration and local full-suite verification.
- [x] Historical iteration-2 build, desktop/mobile browser QA, and video probe/full-decode verification.
- [x] PR1 merged via normal squash after required CI passed; scaffold/PR1 GLM privacy reviews passed.
- [x] PR2 merged per maintainer confirmation.
- [x] Maintainer-reported Chrome playback through authenticated private routing across desktop, portrait, and landscape viewports, including 206 seeking and close cleanup.
- [x] PR4 Aurora and PR5 36-second design merged with privacy review and CI per maintainer confirmation.
- [x] Authorized 36-second 1920x1080/24 fps film, 864 frames, no interpolation/audio, and bounded functional QA.
- [x] Revised 3D depth and airway-only ending, unchanged pre-28-second imagery, and maintainer-confirmed full artifact validation/decode.
- [ ] Whole-implementation GLM privacy gate, subsequent commit/PR submission, and remote CI outcome, owned by the coordinating maintainer; no PR6 result claimed.
- [ ] Non-blocking P2 polish: mobile inline size and some ruler-label offsets; fullscreen/direct play available.
- [ ] Heuristic mask-quality review and refinement, with authorized evidence external.
- [ ] Deferred: reviewed labelmap import and oblique viewing extensions.

## Lessons Learned

- A visual selector must preserve the working surface, not just its state: repaint immediately after canvas resize, and avoid ancestor overflow rules that disable a sticky mobile selector.
- Native and reduced-grid affines differ: source HU and labels have distinct shapes, strides, and spatial transforms. Array indices alone do not establish alignment.
- Manifest-last publication matters: failure tests include partial destination publication without a completed manifest. An incomplete workspace is not a usable build; keep it separate from successful runs.
- Scaffold checks cannot establish runtime geometry or visual quality. Backend synthetic and frontend logic tests add bounded evidence, not anatomical or clinical validation.
