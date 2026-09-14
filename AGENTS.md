# Contributor and Agent Guidelines

The v0.1 backend, CLI (`inspect`, `build`, `serve`, `render-video`), and frontend are implemented. This is a usable local educational CPU heuristic baseline with limited candidate masks, not validated segmentation models. Do not make diagnostic, clinical-quality, or complete-vasculature claims. Video export is implemented; reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling remain unsupported.

## Repository Layout

- `src/ct_education/`: Python CLI, DICOM ingestion, geometry, heuristic segmentation, mesh extraction, path safety, loopback server, and optional video rendering.
- `frontend/`: Vite and Three.js application, with logic tests in `frontend/tests/` and generic build output in `frontend/dist/`.
- `tests/`: Synthetic backend tests and repository hygiene checks.
- `docs/`: Requirements, architecture, tests, and working log. Current source and CLI help determine shipped behavior where a proposal differs.
- `skills/ct_education.md`: The single root skill exposed to agent discovery.

## Environment and Testing

Before Python work, check for `.venv`. If absent, create it with `uv venv`; otherwise activate the existing environment. From the repository root:

```bash
source .venv/bin/activate
uv pip install -e .
npm --prefix frontend ci
npm --prefix frontend run build
```

For optional video rendering, install `uv pip install -e '.[video]'` and `python -m playwright install chromium` in the activated environment. Ensure `ffmpeg` with `libx264` is on `PATH`. See [video setup](README.md#optional-video-dependencies).

Recheck `ct-edu --help` and the `inspect`, `build`, `serve`, and `render-video` subcommand help before changing command examples. Use `uv pip install`, not `pip install`.

```bash
python -B -m unittest discover -s tests -p test_pipeline.py -v
python -B -m unittest discover -s tests -v
CT_EDU_VIDEO_FFMPEG_SMOKE=1 python -B -m unittest discover -s tests -v
npm --prefix frontend test
```

Full discovery includes pipeline, hygiene, and video tests. The opt-in command requires `ffmpeg`; its encoder smoke uses synthetic frames and a mocked browser/server, not browser E2E. The current verified suite is 69 Python tests with the smoke enabled and 32 frontend tests, with zero skips. Default Python discovery skips the one opt-in smoke test. CI runs default Python discovery, `npm test`, and the generic frontend build. All fixtures must be synthetic and generated in memory or external temporary storage, never committed. Logic tests and frontend builds do not establish visual quality or medical accuracy; [test status](docs/test.md) separately records bounded browser verification.

## Working Conventions

- Update the dated changelog in `docs/working.md` after substantive changes; record actual results and pending checks separately.
- Keep public documentation and examples English and ASCII, with fictional `/path/to/...` paths only.
- Preserve concurrent changes. Do not undo another contributor's work.
- Use the existing CLI for authorized local generation; develop checks with synthetic inputs, not private health records.
- Keep native HU and reduced-grid label geometry distinct. Mesh appearance is not source-slice evidence.
- Keep presentation transforms separate from source arrays: physical 2D aspect and superior-up rows require inverse click mapping; display-only mesh smoothing must not modify HU or labels.
- Missing tools or authorized input are blockers, not permission to fabricate outputs or upload private data.

## Git and Protection

Git and remote mutations require explicit user authorization. The user has authorized the current implementation PR/merge iteration; that does not authorize future unrelated mutations. The coordinating maintainer handles Git operations serially. Delegated documentation workers perform no Git mutations.

`master` protection is active, as confirmed by the coordinating maintainer:

- Pull requests required, with `required_approving_review_count: 0`.
- Administrator enforcement enabled: `enforce_admins: true`.
- Required status check: `scaffold-hygiene`.
- Force pushes and branch deletion disabled.

Do not weaken or bypass these protections. Zero required approvals does not permit direct pushes in place of a PR.

## Privacy Gate

Before EVERY pull request, inspect the complete proposed diff and all added files, including ignored or force-added files. Run hygiene checks and manually scan for secrets, private paths, identifiers, identifying case facts, and medical or binary assets. Automated scans and ignore rules are not a privacy guarantee and do not sanitize existing history.

Repository, external read-only input, and external workspace must remain pairwise disjoint after real-path resolution, including aliases and ancestor relationships. Annotations must be external to the repository and workspace; video output resides inside the external workspace. Runtime data always stays external: even sanitized manifests, inventory, labels, meshes, screenshots, tours, and videos must not enter public repositories/history, PRs, issues, docs, examples, CI, logs, or frontend assets. Source mappings belong only in private configuration or private provenance.

Default to local-only with no study uploads. A GPT review may receive only the case material, for the purpose and destination, explicitly approved by the user for that case. General permission to build, test, improve, or release does not authorize uploads; agents cannot infer or self-grant permission. If authorization, material, purpose, or destination is unspecified, stop before transmitting. This documentation grants no case-upload permission and does not approve other remote providers. Review consent never permits public disclosure of raw patient data, derivatives, identifiers, private paths, or case facts. The application has no upload route.

Use the guarded loopback server, not arbitrary directory serving, public tunnels, or hosted demos. Do not print source paths, filenames, identifying headers, or raw private exceptions. Public validation reports contain generic outcomes only. Stop the PR on any unresolved privacy finding without copying the sensitive content into the report.
