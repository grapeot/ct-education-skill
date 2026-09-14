# Working Status

## Current Status

The v0.1.0 backend Python package, `inspect`/`build`/`serve`/`render-video` CLI, and Three.js frontend are implemented and usable for local educational exploration. Video export uses Playwright Chromium and ffmpeg. Segmentation remains a limited CPU heuristic baseline, not validated models or high-fidelity clinical masks. Reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported.

Verification on 2026-09-14: **61 Python tests passed with the opt-in ffmpeg smoke enabled and 27 frontend unit tests passed**, with zero skips, independently rerun by the documentation reviewer. Scanner integration is complete. The coordinating maintainer separately reports successful authorized private generation, desktop/mobile browser QA with no console errors and selection/clipping/candidate focus checked, and video generation. These generic functional outcomes do not certify anatomy or segmentation quality. The final manual privacy gate is next, owned by the coordinating maintainer.

## Changelog

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
- The final manual privacy gate and remote PR/CI outcomes remain the coordinating maintainer's responsibility. No remote CI pass is claimed by this update.
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
- [x] Full 61-test Python suite with encoder smoke and 27 frontend tests.
- [x] Maintainer-confirmed remote `master` protection.
- [x] Scanner integration and local full-suite verification.
- [x] Maintainer-reported desktop/mobile browser QA and video generation.
- [ ] Final manual privacy gate before PR submission; remote CI outcome after submission.
- [ ] Heuristic mask-quality review and refinement, with authorized evidence external.
- [ ] Deferred: reviewed labelmap import and oblique viewing extensions.

## Lessons Learned

- Native and reduced-grid affines differ: source HU and labels have distinct shapes, strides, and spatial transforms. Array indices alone do not establish alignment.
- Manifest-last publication matters: failure tests include partial destination publication without a completed manifest. An incomplete workspace is not a usable build; keep it separate from successful runs.
- Scaffold checks cannot establish runtime geometry or visual quality. Backend synthetic and frontend logic tests add bounded evidence, not anatomical or clinical validation.
