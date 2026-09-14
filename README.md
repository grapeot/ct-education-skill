# CT Education Skill

CT Education Skill is a local educational chest CT application and coding agent skill. **v0.1.0 is usable:** its CPU heuristic pipeline generates limited candidate masks and 3D surfaces, alongside native-grid CT slice views in an interactive local web viewer. These are not validated segmentation models.

## Important Disclaimers

- Educational and technical exploration only, not medical diagnosis, clinical advice, triage, or treatment planning.
- Not a clinically validated viewer. Candidate masks use intensity thresholds and region growing, not trained models or calibrated probabilities.
- No guarantee of complete vasculature; artery-vein classification is not implemented.
- Reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling are not implemented. Browser rendering completion does not establish high-fidelity masks or anatomical accuracy.
- The CPU pipeline needs no GPU or model downloads. The web viewer requires WebGL.

## Candidate Layers

The heuristic pipeline attempts four candidate layers. Empty masks or unsupported surface extraction can omit a layer; inspect the warnings rather than assuming missing anatomy is absent from the source.

- Lung candidates: Thresholded interior air envelopes; incomplete coverage and altered tissue can cause omissions.
- Airway candidates: Bounded low-HU growth from a superior central seed can recover branching candidates. Branch identity and completeness remain unverified.
- Dense intrapulmonary candidates: Dense regions inside eroded lung envelopes; these can include nonvascular tissue.
- Bone candidates: High-HU body components; these can include calcifications and other dense material.

The viewer supports orbit/pan/zoom, layer visibility and opacity, linked slice and voxel selection, window controls, candidate focus, and a local guided tour. RAS x/y/z clipping uses dynamic lighting without baked shadows. Cuts are visibly uncapped: holes at cut boundaries do not represent anatomy.

The optional 3D native-slice plane defaults off for overview/anatomy, while the 2D source panel remains available. Anatomy tour cameras fit the requested layer bounds; candidate focus is separate. Mobile control panels collapse to leave more room for the scene and source panel.

## Source Images and Surfaces

Native source data is preserved as float32 Hounsfield Units (HU) in `volume.npy`, on the source grid `[k,j,i]` without spatial downsampling. Axial views are display-windowed 8-bit PNGs of the selected acquired frame, not original DICOM bytes. Coronal and sagittal views are source-grid cross-sections, not independent acquisitions or anatomical world-axis reformats for oblique data. Numerical HU remains available through voxel selection.

Surfaces are disposable approximations extracted from reduced-grid masks with their own affine and stride. Downsampling can lose small branches; a smooth surface does not prove anatomical completeness or source-image detail. Do not compare native and label-grid array indices directly. The viewer reports 0-based `[i,j,k]` and physical LPS/RAS coordinates in millimeters.

Surfaces now use bounded display-only smoothing; native HU and label arrays are unchanged by that pass. Do not use smoothed surfaces for diagnostic size measurements. Coronal/sagittal 2D views use physical aspect ratios and superior-up presentation, with inverse click mapping. Backend PNG arrays and 3D texture orientation remain unchanged; display scaling and row reversal do not create new source detail or anatomical oblique reformats.

## Installation

Requirements: Python >=3.12, `uv`, Node >=18, and npm. The runtime uses POSIX filesystem APIs and requires an editable source checkout; native Windows support is not provided.

Run from the repository root. Skip `uv venv` if `.venv` already exists and activate it instead:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
npm --prefix frontend ci
npm --prefix frontend run build
```

The last two commands run `npm ci` and `npm run build` in `frontend/`. Generic assets compile into `frontend/dist`; never place study data there. The CLI needs this build to serve the application. `.env.example` is illustrative only: the CLI does not read `.env` or `CT_EDU_WORKSPACE`. Use explicit flags.

### Optional Video Dependencies

Video export via `ct-edu render-video` requires the video extra and a browser binary. In the activated environment:

```bash
uv pip install -e '.[video]'
python -m playwright install chromium
```

An `ffmpeg` executable with `libx264` support must also be available on `PATH` via your system package manager. System and browser dependencies may require platform-specific setup; the render command does not install packages automatically. The built frontend is required.

## Quickstart

All paths below are fictional. Repository, input, and output must be pairwise disjoint after real-path resolution: none may equal, contain, or sit inside another. The workspace parent must exist, but the workspace itself must not exist.

Inspect an external read-only DICOM directory or ZIP archive. A directory can contain loose files and `.zip` packages; frames with the same `SeriesInstanceUID` are combined across packages without extraction. Duplicate SOP frames and duplicate slice positions are rejected instead of deduplicated:

```bash
ct-edu inspect --input /path/to/external/dicom_dir_or_zip
```

Inspect reports series numbers, slice counts, support status, generic reason codes, and skipped files. Keep this runtime inventory private. Supported inputs are consistent single-frame `CTImageStorage`, `MONOCHROME2`, HU-rescaled, near-axial uniform stacks, including supported tilted geometry. Scouts, enhanced/multiframe CT, and inconsistent or nonuniform stacks are rejected. Decoder availability is not universal transfer-syntax support.

Build using the series number selected from inspection. `7` is illustrative, not a recommended series. Without `--series-number`, the CLI chooses the supported series with the most frames, not necessarily the most suitable input for the task. Explicit selection requires a unique matching series number; series are never fused.

```bash
ct-edu build --input /path/to/external/dicom_dir_or_zip --workspace /path/to/external/workspace --series-number 7
ct-edu serve --workspace /path/to/external/workspace --port 8787
```

Open `http://127.0.0.1:8787` and stop the server with Ctrl+C. Use a fresh sibling workspace for every iteration. A failed build can leave an incomplete directory without `manifest.json`; do not serve it or overwrite it automatically.

Optional annotations require another fresh output workspace:

```bash
ct-edu build --input /path/to/external/dicom_dir_or_zip --workspace /path/to/external/workspace-with-annotations --series-number 7 --annotations /path/to/external/annotations.json
```

`--annotations` imports external positions and radii as unverified spheres, not detected or segmented lesions. The [root skill](skills/ct_education.md#external-annotations) documents the checked JSON schema and a fictional example. Input identifiers and free text are replaced with generic candidate text. There are no overwrite, config, threshold, model, or host flags. Check the installed commands with `ct-edu --help` and each subcommand's `--help`.

### Video Export

Render an MP4 tour directly from a completed workspace:

```bash
ct-edu render-video --workspace /path/to/external/workspace
```

The default output is `tour.mp4` inside that workspace. To render another video without overwriting it, choose a new filename:

```bash
ct-edu render-video --workspace /path/to/external/workspace --output /path/to/external/workspace/review.mp4
```

`render-video` starts its own guarded loopback server; there is no need to launch `serve` first. Defaults are 20 seconds, 15 fps, 1280x720, and `--port 0` to select an available port. The full viewport is recorded, including controls and educational warnings, with a timed orbit/tour and source-slice sweep when annotations are absent. This is a presentation of heuristic output, not higher-fidelity segmentation.

Output must be a new `.mp4` inside the external workspace. Relative output paths resolve under it; the parent must already exist. Existing files, symlinks, and traversal are rejected; no overwrite or automatic subdirectory creation is supported. Repository, input, and workspace remain pairwise disjoint, while the video belongs inside the workspace. See [video options](skills/ct_education.md#video-rendering) for limits and output details.

### Optional Video Playback

Workspace MP4 files have no route by default. To enable playback and download of one explicitly chosen file:

```bash
ct-edu serve --workspace /path/to/external/workspace --video-file tour.mp4
```

`--video-file` accepts a relative path to an existing regular `.mp4` inside the completed external workspace. Absolute paths, traversal, symlinks, and non-MP4 names are rejected at startup (`E_VIDEO_FILE`). This selects a single file, not all outputs; HTTP requests cannot select another path.

The viewer enables "Watch the tour" only when video metadata is available and valid. Clicking it loads the player and attempts playback; closing pauses playback and removes its source. Download and native fullscreen controls remain available. Escape closes the modal even from focused video controls, except during native fullscreen, where the browser handles it. Unavailable video leaves the viewer usable. See the [HTTP contract](docs/rfc.md#local-viewer) and [bounded Chrome verification](docs/test.md#visual-qa-and-regressions). The renderer's internal server leaves video disabled, preventing cyclic playback during capture.

## Troubleshooting

The CLI emits fixed error codes with exit code 2 on failure, 0 on success, and 130 on interruption.

| Error | Action |
| --- | --- |
| `E_PATH_OVERLAP` | Separate repository, input, and output roots, including symlink aliases. |
| `E_WORKSPACE_EXISTS` | Choose a fresh sibling workspace. |
| `E_WORKSPACE_PARENT_REQUIRED` | Provide an existing external parent directory. |
| `E_SERIES_SELECTION_AMBIGUOUS_OR_MISSING` | Check inspection output and select a uniquely numbered series. |
| `E_NO_SUPPORTED_CT_STACK` | Check supported input and geometry requirements; do not invent missing geometry. |
| `E_ANNOTATIONS` | Check allowed keys, numeric types, radius, unique IDs, and in-bounds RAS positions. |
| `E_FRONTEND_NOT_BUILT` | Run `npm --prefix frontend ci` and `npm --prefix frontend run build`. |
| `E_PIXEL_DECODE` | Check the transfer syntax and installed decoder locally; do not share private tracebacks. |
| `E_VIDEO_FILE` | Select an existing regular `.mp4` with a workspace-relative path; no absolute paths, traversal, or symlinks. Omit `--video-file` to disable playback. |
| `E_VIDEO_DEPENDENCY_FFMPEG` | Install `ffmpeg` with `libx264` support on `PATH`. |
| `E_VIDEO_DEPENDENCY_PLAYWRIGHT` | Install `'.[video]'` in the activated environment. |
| `E_VIDEO_BROWSER` | Run `python -m playwright install chromium`; check platform browser dependencies and headless execution permissions. |
| `E_VIDEO_OUTPUT`, `E_VIDEO_OUTPUT_EXISTS` | Choose a new `.mp4` under the workspace with an existing parent. |
| `E_VIDEO_DURATION`, `E_VIDEO_FPS`, `E_VIDEO_DIMENSIONS` | Check the documented video option limits. |
| `E_VIDEO_ASSETS`, `E_VIDEO_ENCODER`, `E_VIDEO_RENDER` | Check complete workspace assets, browser loading, and ffmpeg encoding locally. Staging and destination must support same-filesystem hard-link publication. |

## Privacy and Security

Input is read-only to the tool; input content symlinks are rejected. All runtime data stays external, including volumes, masks, meshes, manifests, inventory, annotations, screenshots, tour data, and rendered videos. `provenance.json` contains private source mappings and an algorithm identifier; it is never served. Even sanitized derivatives are private, not public demo assets.

The default is local-only: no study uploads. A GPT review is allowed only with explicit per-case user approval of the material, purpose, and destination. General permission to build, test, improve, or release does not authorize uploads; agents cannot infer or self-grant permission. If any part of that authorization is unspecified, stop before transmitting. This exception does not authorize other providers or public disclosure. Raw patient data, private derivatives, identifiers, paths, and case facts never belong in public repositories/history, PRs, issues, docs, CI, logs, or assets. This documentation is not case-upload authorization, and the application has no upload route.

The server binds only to `127.0.0.1`, checks Host and Origin, and uses `Cache-Control: no-store`. It serves generic frontend assets and allowlisted APIs, not raw volume files, provenance, or directories. Only an explicitly selected `--video-file` MP4 gains playback/download routes. Container metadata stripping is not anonymization, and loopback controls are not user authentication.

Static workspace serving, public tunnels, and public hosting remain prohibited. User-authorized private access through caller-managed authenticated routing may include the chosen MP4, without adding routes for other output files. A local reverse proxy must forward `Range` and preserve `Cache-Control: no-store`; deployment configuration stays private. There is no runtime CDN, telemetry, or cloud tour service.

## Agent Skill Integration

Give this checkout to your coding agent and ask it to install the skill. The installer should read the caller's `AGENTS.md` or `CLAUDE.md` and routing files first, then register exactly one root skill, [`skills/ct_education.md`](skills/ct_education.md), in `rules/skills/INDEX.md` or `skills/INDEX.md`. If neither exists, add one pointer in `AGENTS.md` or `CLAUDE.md`. Keep caller-specific paths and mappings in private configuration.

## Documentation and License

- [Product requirements](docs/prd.md)
- [Technical architecture](docs/rfc.md)
- [Tests and verification](docs/test.md)
- [Working status](docs/working.md)
- [Contributor rules](AGENTS.md)

[MIT License](LICENSE). Copyright 2026 CT Education Skill contributors.
