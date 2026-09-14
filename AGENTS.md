# Contributor and Agent Guidelines

## Layout and Status

This is an English, public-ready scaffold, not a working CT application. `src/` and `scripts/` are reserved placeholders; there is no runtime package or CLI. `docs/` holds requirements, architecture, tests, and the working log. `tests/` holds offline hygiene checks. Expose exactly one root skill, `skills/ct_education.md`; no focused skills exist.

## Environment

Before Python work, check for `.venv`. If absent, create it with `uv venv --python 3.12`; activate it with `source .venv/bin/activate`. If dependencies are later needed, use `uv pip install`, not `pip install`. Current tests require only the Python standard library:

```bash
python -B -m unittest discover -s tests -v
```

Tests run offline and generate only synthetic hygiene probes in external temporary storage. Passing them does not validate geometry, runtime privacy, segmentation, or clinical quality. CI runs `scaffold-hygiene` for pushes and PRs to `master`, with no deployments or artifact uploads.

## Working Conventions

- Update the dated changelog in `docs/working.md` after every substantive change; record actual outcomes, not planned tests as passes.
- No Git mutations without explicit authorization. This scaffold performs no initialization, commits, pushes, remote creation, or branch configuration; the coordinating maintainer handles Git serially.
- Keep docs and examples English, with fake configuration only. Never read health records or real DICOM to develop scaffold checks.
- Future runtime behavior must follow `docs/rfc.md`; its safety contract is not implemented yet.

## Privacy Gate Before Every PR

Repository, external read-only input, and external output workspace must remain pairwise disjoint after real-path resolution. No medical assets or identifying case facts belong in this repository, public app assets, docs, examples, logs, CI, or remote AI tools. Derived volumes, labelmaps, meshes, screenshots, tours, and videos are also private external outputs. Private aliases and source mappings stay in caller-owned private configuration.

- Inspect the complete proposed diff and all added files, including ignored or force-added files, before EVERY pull request.
- Run hygiene checks and scan for secrets, identifiers, private paths, and medical or binary assets. Manually review the text and test output; automated scans are not a privacy guarantee.
- Never attach studies or private derivatives to issues, PRs, or CI. Do not print source paths, filenames, identifying headers, or raw exceptions; planned local logs use aggregate counts and error codes.
- Ignore rules cover `workspace`, `workspaces`, `data`, `input`, `output`, `artifacts`, and `private` anywhere, plus medical/binary suffixes. Ignore rules do not sanitize already tracked files or replace review.
- Stop a PR if any privacy finding remains unresolved. Record only a generic result, not the sensitive content itself.

## Branch Policy

Pending remote configuration: `master` must require a PR even when zero approvals are required. Enforce protection for administrators, require the `scaffold-hygiene` status check, and disallow bypasses, force pushes, and deletion. Do not claim this policy is active until the coordinating maintainer configures and verifies it remotely.

## Failure Handling

If necessary tools or authorized external data are missing, report the missing capability without fabricating results or uploading data. Do not implement or run the proposed application merely because its future commands appear in the docs.
