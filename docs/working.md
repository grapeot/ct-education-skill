# Working Status

## Current Status

Phase 0 scaffold only. No runnable CLI, CT processing, viewer, server, or video export exists. `src/` and `scripts/` remain placeholders. Git and remote configuration are outside this scaffold's scope.

## Changelog

### 2026-09-14

- Added English requirements, architecture, contributor rules, one root skill, and MIT license.
- Defined external-only data boundaries, native geometry, candidate uncertainty, and local viewer requirements.
- Added offline standard-library hygiene tests and a `master` CI workflow without publishing or artifact uploads.
- Validation: Python 3.12.9 in a uv-managed `.venv`; `python -B -m unittest discover -s tests -v` passed all 9 hygiene tests, with zero skips.
- Separate bounded private-path, email, and credential-marker scan found zero matches in scaffold files. Manual review found no medical assets or identifying case facts. This is not a guarantee against arbitrary sensitive text.
- No linter is configured. Application tests and remote CI have not run; branch protection is not configured by this scaffold. No Git commands were performed.

## Phased Plan

- [x] Scaffold: documentation, license, configuration example, single root skill, tests and CI definition.
- [ ] MVP: fail-closed paths and geometry, CPU candidates, reviewed-label imports, linked slices/3D, local guided tour.
- [ ] QA: synthetic geometry/privacy/segmentation/UI checks and separately authorized local review.
- [ ] Video: optional downstream Blender and `render-video` after MVP and QA.
- [ ] Coordinating maintainer: serial Git setup and remote `master` protection, PR required with zero approvals allowed, administrator enforcement, and required `scaffold-hygiene` check.

## Lessons Learned

No runtime experiments have been performed. There are no observed CT-processing lessons yet. Passing scaffold checks must not be reported as geometry, privacy-runtime, or segmentation validation.
