# Test Plan

## Current Checks

Only scaffold hygiene tests exist. No parser, geometry, segmentation, runtime privacy, integration, or viewer end-to-end tests are implemented. A passing scaffold suite is not clinical validation or proof that arbitrary identifying text is absent.

Create `.venv` with `uv venv --python 3.12` if absent, then run:

```bash
source .venv/bin/activate
python -B -m unittest discover -s tests -v
```

The suite uses Python standard-library `unittest` without third-party dependencies or network calls. It checks the required scaffold and single root skill, fake configuration, license, CI policy text, ignore-rule declarations, ASCII text inventory, and generic private-text markers. Synthetic hygiene probes exercise rejected filenames, directory names, binary content, symlinks, and private-text patterns in external temporary storage. No DICOM is generated or read by these checks.

Ignore checks verify declarations, not Git's full ignore engine. The repository scan skips local environment, cache, and Git metadata directories; before every PR, manually review all proposed tracked files, including force-added files and those outside the scan. Pattern checks cannot detect every identifier or identifying case fact.

CI runs a single `scaffold-hygiene` job on pushes and PRs to `master`, with no deployments or artifact uploads. CI has not run remotely during scaffolding. The branch protection policy is separately configured and verified by the coordinating maintainer.

## Future Unit and Integration Coverage

- Generate synthetic volumes at test time in memory or external temporary directories; no stored medical fixtures. Use known HU values and geometric primitives.
- Verify signed-pixel HU conversion, rescale values, scrambled slice sorting, anisotropic and oblique grids, and actual IPP displacement rather than `SliceThickness`.
- Exercise independent series, duplicate/gapped/nonuniform stacks, changing orientation, and unsupported multiframe rejection.
- Roundtrip voxel centers through LPS and viewer transforms within a declared numerical tolerance; select the original frame for known clicks and reject out-of-bounds positions.
- Reject equal/nested roots in both directions, symlink aliases, missing-leaf escapes, traversal, and output path replacement. Check that rejected writes leave input and repository unchanged.
- Test CPU thresholds, chest masks, connected components, seeded region-growing leakage, and empty/ambiguous results. Missing warning flags must not be interpreted as confirmed anatomy.
- Reject reviewed-label imports with mismatched shape, geometry, series, or missing provenance; retain review status without treating it as truth.
- Capture logs and network requests on synthetic runs; verify no identifying fields, source paths, non-loopback traffic, or arbitrary file-serving routes.

## Future End-to-End and Manual QA

End-to-end tests await a viewer implementation. They must verify layer toggles, dynamic cuts, original-slice linkage, source-coordinate picking, uncertainty text, and tour stops on synthetic data. Test desktop and mobile layouts, loopback host/origin checks, and absence of study data from app builds and persistent caches.

Real-study evaluation requires separate authorization and local private storage. Manually inspect slice/label overlays, geometry alignment, leakage, missing branches, and tour claims. Keep all study images, screenshots, meshes, tours, and video outside the repository and public PR/CI attachments. Record only generic pass/fail summaries publicly. Optional video QA comes after MVP and QA, and must verify source-coordinate continuity and candidate labels.
