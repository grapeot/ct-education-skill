---
name: ct-education
description: Use the existing ct-edu CLI for local educational chest CT exploration, native-slice linkage, limited CPU candidate masks, video rendering, and quality iteration in external private workspaces.
---

# CT Education Skill

## Goal and Status

Use the existing CLI to inspect authorized external CT, build source-linked candidate surfaces, explore them locally, render educational video tours, and improve mask quality with verifiable external experiments. **v0.1.0 is implemented and usable**, with `inspect`, `build`, `serve`, and `render-video`. It is not a validated segmentation model. Do not reimplement the application just to generate a workspace.

Type: Workflow / Tool. Outputs: external private workspace only. Created and updated: 2026-09-14. Expose only this root skill to agent discovery.

## Boundaries

- Education and technical exploration only, not diagnosis, clinical advice, triage, or treatment planning. This is not a clinically validated viewer.
- CPU thresholds, body envelopes, components, and seeded air propagation produce limited lung, airway, dense intrapulmonary, and bone candidates. Masks can leak or omit structures; dense intrapulmonary regions can be nonvascular. No trained models, calibrated probabilities, full vascular completeness, or artery-vein classification are provided.
- Reviewed labelmap import, arbitrary oblique clipping, and anatomical oblique resampling are not implemented. No GPU/model download is needed for processing; the viewer requires WebGL. Rendering completion does not establish high-fidelity masks.
- DICOM input is external and read-only. Repository, input, and output must be pairwise disjoint after real-path resolution, including equality, aliases, and ancestor relationships. Annotation files must be external to the repository and output. Input content symlinks are rejected.
- Runtime data always stays external, including inventory, manifests, masks, meshes, screenshots, tours, and videos. Video output belongs inside the completed external workspace. No raw patient data, private derivatives, identifiers, case facts, or private paths in public repositories/history, PRs, issues, docs, examples, CI, logs, or frontend assets. Private aliases stay in caller configuration.
- Default to no study uploads. A GPT review may receive only the material, for the purpose and destination, explicitly approved by the user for that case. General permission to build, test, improve, or release is not upload consent; agents cannot infer or self-grant permission. Stop before transmitting if any authorization scope is unspecified. This skill is not case-upload authorization, approves no other providers, and never permits public disclosure. The application has no upload route.
- Use the guarded loopback server; no static workspace serving, public tunnels, or public hosting. User-authorized private access through caller-managed authenticated routing may include one explicitly chosen MP4, not all outputs. Local reverse proxies must forward `Range` and preserve `Cache-Control: no-store`; keep deployment configuration private. Git/remote mutations require explicit authorization under [contributor rules](../AGENTS.md), and must be coordinated serially.

## Resources

- [Installation and troubleshooting](../README.md), [requirements](../docs/prd.md), [tests](../docs/test.md), and [working status](../docs/working.md).
- [CLI](../src/ct_education/cli.py), [DICOM geometry](../src/ct_education/dicom.py), [build/annotation contract](../src/ct_education/pipeline.py), [segmentation and mesh extraction](../src/ct_education/segmentation.py), [video rendering](../src/ct_education/video.py), [path safety](../src/ct_education/safety.py), and [HTTP server](../src/ct_education/server.py).
- [Frontend](../frontend/) and [architecture](../docs/rfc.md). Use current source and help as authority where proposals differ.

Run `ct-edu --help`, `ct-edu inspect --help`, `ct-edu build --help`, `ct-edu serve --help`, or `ct-edu render-video --help` for exact installed flags.

## Setup

Use Python >=3.12, `uv`, Node >=18, and npm in an editable source checkout with POSIX filesystem support. From the repository root, create `.venv` only if absent:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
npm --prefix frontend ci
npm --prefix frontend run build
```

If `.venv` exists, skip creation and activate it. The npm commands run installation and build in `frontend/`. Keep its build generic. `.env.example` is not consumed by the CLI; use explicit flags.

For optional video rendering, in the activated environment:

```bash
uv pip install -e '.[video]'
python -m playwright install chromium
```

Install `ffmpeg` with `libx264` on `PATH` using your system package manager. Browser/system dependencies may need platform-specific setup; `render-video` does not install them automatically.

## CLI Use

### Inspect and Build

All example paths and the series number below are fictional. Inspect an external DICOM folder or ZIP. Folders can contain loose files plus ZIP packages; matching-series frames are combined across packages without extraction. Different series remain separate, and duplicate SOP frames/positions are rejected rather than deduplicated:

```bash
ct-edu inspect --input /path/to/external/dicom_dir_or_zip
ct-edu build --input /path/to/external/dicom_dir_or_zip --workspace /path/to/external/workspace --series-number 7
```

Inspection reports series numbers, slice counts, support status, generic reasons, and skipped files. Keep the inventory private. Explicit selection requires a unique matching series number. Without it, build selects the supported series with the most frames, not a suitability recommendation. Independent series are not fused.

Supported stacks are consistent, single-frame `CTImageStorage`, `MONOCHROME2`, HU-rescaled, near-axial uniform grids, including supported oblique/tilted displacement. Scouts, enhanced/multiframe, duplicate positions, and inconsistent/nonuniform geometry are rejected. Physical positions and orientations determine ordering, not filenames or `SliceThickness`. Unsupported geometry is a blocker, not permission to guess an affine.

The workspace parent must exist; the target workspace must not exist. Choose a fresh sibling for each run and preserve previous outputs for comparison. Do not automatically delete or overwrite a failed or prior build.

### External Annotations

`--annotations` imports positions and radii as unverified candidate spheres, not segmented lesions or automatic detection:

```bash
ct-edu build --input /path/to/external/dicom_dir_or_zip --workspace /path/to/external/workspace-with-annotations --series-number 7 --annotations /path/to/external/annotations.json
```

The external JSON is an array of at most 100 objects. This fictional example illustrates its structure:

```json
[
  {
    "id": "example-1",
    "position_ras": [0.0, 0.0, 0.0],
    "radius_mm": 3.0
  }
]
```

The origin may not lie inside the selected scan. Replace it with a verified in-bounds RAS position from the authorized workspace; do not reuse the example as a case annotation.

| Field | Constraint |
| --- | --- |
| `id` | Required, unique ASCII string of at most 64 characters: letters/digits/hyphen/underscore, with at least one alphanumeric character. |
| `position_ras` | Required list of three finite numbers, millimeters in RAS, within the native grid's half-voxel bounds after inverse affine mapping. |
| `radius_mm` | Required finite number, greater than 0 and at most 100. |
| `label`, `description`, `review_status` | Optional; caller text is not retained in served output. |

No other keys are allowed. Served IDs become `candidate-1`, `candidate-2`, and so on, with generic labels/descriptions and `unverified candidate` status. Sanitization does not make coordinates or derived geometry public data.

### Serve and Explore

```bash
ct-edu serve --workspace /path/to/external/workspace --port 8787
```

Open `http://127.0.0.1:8787`; stop with Ctrl+C. To view the annotation build, pass its workspace instead. The port defaults to 8787. The server is loopback-only with no host override or public publishing option.

Optionally enable playback/download of one chosen MP4:

```bash
ct-edu serve --workspace /path/to/external/workspace --video-file tour.mp4
```

Video is disabled by default. `--video-file` accepts a relative path to an existing regular `.mp4` inside the completed workspace; absolute paths, traversal, symlinks, missing files, and non-MP4 names fail startup with `E_VIDEO_FILE`. HTTP requests cannot choose another file. `/api/video-info` returns `{"available":false}` by default or the fixed playback/download URLs when configured; this does not validate codec playability. See the [HTTP contract](../docs/rfc.md#local-viewer) for GET/HEAD and single-range 206/416 behavior.

"Watch the tour" enables only for valid same-origin metadata. Clicking opens the player and attaches its source; closing pauses playback, removes the source and download link, reloads the element, and restores focus. Download and native fullscreen controls remain available. Escape closes the modal from focused video controls unless native fullscreen is active, when browser Escape behavior is preserved. No media source is attached before the click; unavailable video does not disable the viewer.

Explore layer toggles/opacity, native slice indices/windowing, source-linked picks, annotation focus, and tour stops. Minimal manifest tours are expanded with available-layer/source stops; sufficiently complete tours are not duplicated. RAS x/y/z clipping is uncapped, and clipped-away mesh hits are filtered from picking. Do not interpret cut holes as anatomy. Interactive camera transitions depend on the current view; video rendering separately controls frame time.

The 3D native-slice plane is optional and defaults off for overview/anatomy; the 2D source panel remains available. Anatomy tour cameras fit actual requested layer bounds, while candidate focus remains separate. Mobile panels collapse to reduce obstruction.

The read-only image APIs are `/api/manifest`, `/api/mesh/<layer-id>`, `/api/slice?axis=axial&index=0&wc=-600&ww=1500`, and `/api/voxel?i=0&j=0&k=0`. Slice axis also accepts `coronal` and `sagittal`; `wc`/`ww` default to the shown values. Slice responses are PNG with `X-Slice-Index`; voxel responses contain `hu`, `lps`, and `ras`. Raw volumes, labels, and provenance are not served.

### Video Rendering

Render a completed workspace; the command starts its own guarded loopback server, so `serve` does not need to be running:

```bash
ct-edu render-video --workspace /path/to/external/workspace
```

To render another version, use a new output filename. This example explicitly shows the default rendering options, not a private run's parameters:

```bash
ct-edu render-video --workspace /path/to/external/workspace --output /path/to/external/workspace/review.mp4 --duration 20 --fps 15 --width 1280 --height 720
```

| Option | Default | Constraint |
| --- | --- | --- |
| `--workspace` | Required | Existing completed external workspace. |
| `--output` | `tour.mp4` inside workspace | New `.mp4` inside the workspace. Relative paths resolve under it; parent must exist. No overwrite, symlinks, traversal, or automatic subdirectory creation. |
| `--duration` | `20` | Finite seconds, greater than 0 and at most 120. |
| `--fps` | `15` | Integer from 1 to 60. |
| `--width` | `1280` | Even integer from 2 to 1920. |
| `--height` | `720` | Even integer from 2 to 1080. |
| `--port` | `0` | Integer from 0 to 65535; 0 selects an available port, unlike `serve`'s default 8787. |

Frame count is `ceil(duration * fps)` and resulting duration is `frames / fps`. Successful stdout is JSON with `status: complete`, `frames`, `fps`, `duration`, `width`, and `height`, not the output path. Keep runtime results private.

The full viewport is captured, including UI and educational warnings. A frame-stepped orbit/tour is used; without annotations it also sweeps source slices, while annotation tours retain their selection. This provides an explicit timeline, not a byte-identical cross-platform rendering guarantee. ffmpeg encodes no-audio H.264 (`libx264`, `yuv420p`, CRF 20, faststart MP4); metadata stripping does not anonymize visible content.

The browser profile and temporary output are staged privately as a sibling of the external workspace. Publication uses an exclusive hard link with owner-only `0600` mode, so staging and destination must share a filesystem supporting hard links. Existing output is never overwritten, even if created during capture. Browser/server/encoder resources and temporary data are cleaned up on completion or handled failure. The capture browser allows only its exact loopback origin's GET/HEAD requests and blocks WebSockets/service workers; this is not OS-wide network isolation. Its internal server uses default `video_file=None` to avoid cyclic playback during generation. MP4 serving requires a separate explicit `serve --video-file` selection.

## Coordinates and Outputs

Native array order is `[k,j,i]`; the affine maps homogeneous `[i,j,k,1]` to millimeter coordinates. Indices are 0-based. `affine_ras = diag(-1,-1,1,1) @ affine_lps`. LPS-to-RAS changes the signs of the first two physical axes, not the array ordering.

Axial PNGs are display-windowed acquired frames from `volume[k,:,:]`, not original DICOM bytes. Coronal `volume[:,j,:]` and sagittal `volume[:,:,i]` are source-grid cross-sections, not independent acquisitions or anatomical world-axis reformats for oblique data. Backend planes are not flipped or resampled. Browser display scaling is not new source detail; numeric HU comes from the voxel API, not the 8-bit PNG.

The 2D canvas uses physical aspect ratios and superior-up non-axial row presentation, with inverse click mapping. Display rows reverse when `affine_ras[2][2] > 0`; native PNG arrays and 3D texture UVs remain unchanged. This is not anatomical oblique resampling or full grid de-shearing.

Completed external workspaces contain:

| Artifact | Contract |
| --- | --- |
| `manifest.json` | `schema_version: 1`, native `shape`/`spacing` in `[k,j,i]` order, LPS/RAS affines, `bounds_ras`, `layers`, `annotations`, `warnings`, CT source summary, and embedded `tour`. Published last as completion marker. No separate `tour.json`. |
| `volume.npy` | Native-grid float32 HU cache without spatial downsampling. |
| `labels.npy` | Reduced-grid uint8 bitfield, not mutually exclusive class IDs. Bit values: lungs 1, airways 2, vessels 4, bones 8. |
| `labels-grid.json` | Label `shape`, `affine_lps`, `stride_kji`, `encoding: bitfield`, and `bits` mapping. |
| `meshes/<layer-id>.json` | Flat RAS millimeter `positions` and triangle `indices`. Disposable reduced-grid derivatives; empty or over-budget surfaces can be omitted. |
| `provenance.json` | Private source mappings and `cpu-threshold-v1` algorithm record. Never served or shared publicly. |
| `tour.mp4` or chosen MP4 name | Optional private video output created by `render-video`, inside the completed workspace. Not a manifest asset; playback/download requires explicit `serve --video-file` selection. |

Even the sanitized manifest is private runtime data. Source HU is the intensity reference; the reduced-grid label affine is the spatial reference for masks. Downsampled surfaces cannot establish small-branch completeness.

## Quality Iteration

There are no threshold, model, or mask-import CLI flags. For authorized mask experiments, use the existing functions from `ct_education.segmentation` in an external script: `segment(volume, affine_lps)` returns masks, label affine, stride, and warnings; `mesh_for_mask(mask, affine_lps, native_shape=None, stride=None, smooth=True)` extracts the derivative surface. Pass the label affine for a reduced-grid mask, not the native affine. Set `smooth=False` for raw-mesh comparison; the default is one display-only pass with vertex movement capped at 0.75 mm or a smaller grid-dependent limit before JSON rounding. HU and labels are unchanged by that pass. The returned mask names match the documented layer IDs.

Choose experiments and tests according to the observed failure. Preserve native HU, write experiments to fresh external run directories, and record local parameters, warnings, available layers, missing structures, and leakage. Compare masks against native slices by mapping through their affines; for categorical display, avoid interpolation that invents labels. Change masks and regenerate dependent labels/meshes/metadata consistently, rather than improving only mesh appearance. An experimental script is not automatically a CLI-compatible completed workspace.

Integrate reusable source changes only when authorized. Once integrated, use a fresh CLI build to obtain a consistent viewer workspace. Keep source-specific tuning, local overlays, screenshots, and detailed provenance in the external experiment. Run comparable synthetic checks before attributing an improvement to the method:

```bash
python -B -m unittest discover -s tests -p test_pipeline.py -v
npm --prefix frontend test
```

Use `python -B -m unittest discover -s tests -v` for the full Python suite. With `ffmpeg` available, prefix it with `CT_EDU_VIDEO_FFMPEG_SMOKE=1` to include real encoding of synthetic frames; the smoke still uses a mocked browser/server. All 89 Python and 42 frontend tests passed in the independent rerun with zero skips. Default Python discovery skips that one smoke test. See [test status](../docs/test.md) for maintainer-reported Chrome playback checks through authenticated private routing across desktop, portrait, and landscape viewports. Those checks are not iPhone Safari certification; neither unit nor browser checks certify segmentation quality for a new input.

## Learned Pitfalls

- Anisotropic rasters need physical canvas aspect from affine axis lengths, not square display pixels. Keep native PNGs intact and invert presentation transforms when mapping clicks.
- An off-slice selection is not a current-slice crosshair. Moving the slice must update the selected index, discard stale HU/coordinates, and reject superseded responses before showing new values.
- Shader clipping does not automatically filter raycasts. Exclude discarded mesh hits and hidden 3D slice planes from picking; disabling the optional plane must not disable the 2D source panel.
- Split ZIP packages can contain one series, not separate acquisitions. Use collection ingestion and retain duplicate SOP/position rejection rather than concatenating or deduplicating frames manually.

## Acceptance and Handoff

- The inspected series selection is understood, the CLI exits 0, and a completed `manifest.json` and referenced artifacts exist in a fresh external workspace. Incomplete destinations are not served.
- Known synthetic points roundtrip through native/label/viewer transforms within the relevant tests' tolerances; voxel HU and slice indices match the source. No geometry is invented to accept unsupported input.
- Candidate method/status and limits remain visible. Layer omissions, leakage, reduced-grid detail loss, and uncapped cuts are disclosed rather than hidden by appearance.
- Browser checks cover source-linked selection, layer controls, cuts, focus/tour, and desktop/mobile loading when visual QA is in scope. Retain evidence privately; mark unperformed checks pending, not passed.
- Requested video completes without errors, produces a playable MP4 under the workspace with owner-only permissions, and retains legible UI warnings and source linkage. Check reported frame count/duration against the requested options; do not mistake successful encoding for anatomical validation.
- No runtime assets or identifying facts enter the repository or public history/logs. No remote review occurs without the explicit per-case approval defined above. Every PR receives the manual privacy review in `AGENTS.md`.

Return external artifact locations privately to the authorized caller, with the method, observed limitations, exact tests performed, and remaining work. Do not copy private provenance or case details into public status. A generation can be complete while visual or mask-quality acceptance remains pending; say which stage is complete.

## Failure Handling

CLI failures use fixed `E_*` codes and exit 2; interruption returns 130. Use [troubleshooting](../README.md#troubleshooting) for path, selection, annotation, decoder, frontend, and `E_VIDEO_*` dependency/output/capture/encoding errors. A failed build publication can leave an incomplete destination without a manifest; preserve it and use a new workspace. Video failures do not require rebuilding a valid source workspace; resolve the error and choose a new MP4 name if an output already exists. Never claim success or delete prior output automatically.

Missing tools or authorized input are blockers. Report the missing capability or generic error without fabricating results, searching for unrelated health records, or uploading source paths, identifiers, and private tracebacks. Stop publication on unresolved privacy findings.
