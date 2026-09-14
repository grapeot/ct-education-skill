# Technical Architecture

**Status: implemented v0.1.0.** The CLI provides `inspect`, `build`, `serve`, and `render-video`. It inventories supported CT stacks, builds external candidate assets, hosts a guarded loopback viewer, and optionally exports an educational MP4 with Playwright Chromium and ffmpeg. CPU heuristic masks are limited candidates, not validated models or clinical-quality anatomy. Reviewed labelmap import and arbitrary oblique viewing extensions remain unsupported.

## CLI Interface

Run from an editable source checkout. Create `.venv` only if absent; otherwise activate it:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
npm --prefix frontend ci
npm --prefix frontend run build
ct-edu inspect --input /path/to/external/dicom-or-zip
ct-edu build --input /path/to/external/dicom-or-zip --workspace /path/to/external/new-workspace --series-number 7
ct-edu serve --workspace /path/to/external/new-workspace --port 8787
```

All paths and the series number are fictional. `inspect` requires no output workspace and returns series numbers, slice counts, support status, skipped-file counts, and fixed reason codes, not source names or identifying headers. Treat even that inventory as private runtime output. Explicit `--series-number` requires a unique matching series; otherwise build chooses the supported series with the most frames, not necessarily the most suitable input.

Input can be a DICOM directory containing loose files and ZIP packages, or a single ZIP. Frames with matching `SeriesInstanceUID` can span packages and are read without extraction; different series remain separate. Duplicate SOP instances and duplicate positions are rejected rather than deduplicated. Archive path, size, and symlink checks apply to each ZIP; ZIP-inside-ZIP recursion is not implemented.

The workspace parent must exist; the target must not. Build uses a private staging sibling, then an exclusively created destination. Files are moved into it with `manifest.json` last as the completion marker. Interrupted publication can leave an incomplete destination without a manifest; it cannot be served or overwritten by another build. Preserve it and use a new destination after investigating the failure.

## Source Truth and Geometry

Supported inputs are consistent single-frame `CTImageStorage`, `MONOCHROME2`, HU-rescaled, near-axial uniform stacks. Supported oblique/tilted displacement is preserved. Scouts, enhanced/multiframe data, duplicate positions, changing orientations, and nonuniform displacement are rejected. JPEG Lossless decoding uses pydicom and pylibjpeg-libjpeg; installed decoder support is not a guarantee for every transfer syntax. Unsupported intensity transforms or geometry fail closed.

Raw pixels convert through `HU = pixel_value * RescaleSlope + RescaleIntercept`, respecting signed representation and per-frame rescale values. The slice normal is `cross(IOP[0:3], IOP[3:6])`, where IOP is `ImageOrientationPatient`. Frames are sorted by projecting IPP (`ImagePositionPatient`) onto that normal, not by filename, `InstanceNumber`, or `SliceThickness`.

Array storage is `[k,j,i]`: 0-based column `i`, row `j`, and sorted slice `k`. Native LPS (left, posterior, superior) millimeters follow:

```text
P_LPS = IPP[k]
      + i * PixelSpacing[1] * IOP[0:3]
      + j * PixelSpacing[0] * IOP[3:6]
```

The affine maps homogeneous `[i,j,k,1]` to LPS. Its slice column uses the actual adjacent IPP displacement. Viewer coordinates use RAS (right, anterior, superior) millimeters:

```text
lps_to_ras = diag(-1, -1, 1, 1)
affine_ras = lps_to_ras * affine_lps
P_RAS_homogeneous = affine_ras * [i, j, k, 1]
ras_to_lps = diag(-1, -1, 1, 1)
```

A continuous mesh hit maps through the inverse source affine to fractional `[i,j,k]`. Nearest-voxel selection uses JavaScript `Math.round`, with ties toward positive infinity, then rejects out-of-bounds rounded indices rather than clamping. Fractional coordinates and selected-voxel HU/LPS/RAS are shown separately. Clipped-away mesh hits are filtered before selection.

Native source HU is the intensity reference. Reduced-grid labels have their own stride and affine; do not align masks and native images by matching array indices. Labels are not clinical ground truth, and meshes are disposable rendering derivatives. Source HU must not be changed to improve mesh appearance.

Lung envelope opening/closing and bulk-air detection use spacing-aware physical disk footprints; not every segmentation operation is physically calibrated. Airway candidates use face-connected 2D low-HU pockets, followed by 26-connected propagation and final component filtering. A superior central seed follows the affine direction. Pocket dimensions/location, bulk-lung rejection, and growth volume/cross-section limits constrain expansion; excessive growth falls back to conservative pockets or an empty result. Warnings disclose missing seeds, overgrowth, or lack of sustained bifurcation. Branches can be recovered, but their identity/completeness remain unverified.

`mesh_for_mask(mask, affine_lps, native_shape=None, stride=None, smooth=True)` applies one display-only Laplacian pass: `displacement = 0.3 * (neighbor_mean - original)`. Displacement magnitude is capped at `min(0.75 mm, 0.35 * smallest singular value of the label affine's 3x3 matrix)` before four-decimal JSON rounding. Native HU and label arrays are unchanged by smoothing. Use programmatic `smooth=False` for raw-mesh comparison; there is no CLI smoothing flag. Smoothed surfaces are not suitable for diagnostic size measurements.

## Filesystem and Privacy

Repository, external read-only input, and external workspace must be pairwise disjoint after real-path resolution, including equality, aliases, and ancestor relationships. Descriptor-relative no-follow access and repeated path/identity checks reject tested symlink and replacement cases; they do not establish immunity to every filesystem race. Data paths inside the repository are rejected. Build destinations and video output files cannot overwrite existing targets. Video files belong inside the completed external workspace, not in a disjoint output root.

Default to local-only with no study uploads. GPT review requires explicit per-case user approval of the material, purpose, and destination. General build/test/improvement/release authorization is not upload consent, and agents cannot infer or self-grant permission. Stop before transmission if scope is unspecified. This documentation grants no case-upload permission and approves no other provider. Review consent never permits raw patient data, private derivatives, identifiers, paths, or case facts in public repositories/history, PRs, issues, docs, examples, CI, logs, or assets. Local runtime files remain external; the application contains no upload route.

Private source lookup and caller mappings belong in external private storage, not public configuration. CLI failures expose fixed `E_*` codes and exit 2, not private paths, headers, or tracebacks. Interruptions return 130. Ignore rules and automated scans are defense in depth; the [manual privacy gate](../AGENTS.md#privacy-gate) remains mandatory before every PR.

## External Artifacts

- `manifest.json`: `schema_version: 1`, `shape`, `spacing`, `affine_lps`, `affine_ras`, voxel-cell `bounds_ras`, `layers`, `annotations`, `warnings`, aggregate `source`, and inline `tour`. Spacing is the affine column lengths in `[k,j,i]` order, not necessarily world-axis distances. No separate `tour.json` is emitted.
- `volume.npy`: Native-grid float32 HU in `[k,j,i]` order, without spatial downsampling.
- `labels.npy`: Reduced-grid uint8 bitfield, with bit values lungs=1, airways=2, vessels=4, bones=8. Masks can overlap; these are not mutually exclusive class IDs.
- `labels-grid.json`: Label `shape`, `affine_lps`, `stride_kji`, `encoding: bitfield`, and `bits` mapping.
- `meshes/<layer-id>.json`: Flat RAS-mm `positions` and triangle `indices`. Extraction is bounded to 180,000 triangles per layer; empty or unsupported surfaces can be omitted with warnings.
- `provenance.json`: Private source-frame mappings and algorithm record (`cpu-threshold-v1`), never served.
- `tour.mp4` or chosen MP4 filename: Optional private video output under the workspace, not a served manifest asset.

`build --annotations` accepts an external JSON array of at most 100 objects. Required fields are a unique ASCII `id` (at most 64 letters/digits/hyphens/underscores with at least one alphanumeric), finite three-number `position_ras`, and finite `radius_mm` in `(0,100]`. Centers must be inside native voxel-cell bounds. Optional `label`, `description`, and `review_status` are accepted; other keys are rejected. IDs and free text are replaced with generic candidate text in the served manifest. Spheres remain unverified candidates, never segmented lesions. The [root skill](../skills/ct_education.md#external-annotations) provides a fictional schema example.

## Local Viewer

`serve` binds only to `127.0.0.1`, default port 8787, and validates loopback Host/Origin headers against the actual port. Static routes are `/`, `/index.html`, and allowlisted hashed assets under `/assets/`; source maps and directory listings are not served. Runtime GET routes are:

- `/api/manifest`: The versioned viewer manifest.
- `/api/mesh/<layer-id>`: A listed layer's RAS mesh.
- `/api/slice?axis=axial&index=0&wc=-600&ww=1500`: Display-windowed 8-bit PNG with `X-Slice-Index`. Axis also accepts `coronal` or `sagittal`; window parameters default to the shown values.
- `/api/voxel?i=0&j=0&k=0`: `{hu, lps, ras}` for in-bounds integer native indices.

Responses use `Cache-Control: no-store`. Raw DICOM, volume arrays, labels, provenance, and video files have no route. Loopback guards are not user authentication or full anonymization. No public tunnel, hosting, telemetry, runtime CDN, or cloud tour service is part of the application.

Slice extraction is axial=`volume[k,:,:]`, coronal=`volume[:,j,:]`, sagittal=`volume[:,:,i]`, without backend flips or spatial resampling. Axial PNGs show windowed acquired frames, not original DICOM bytes. Other axes are source-grid cross-sections, not independent acquisitions or anatomical world-axis reformats for oblique data. Numerical HU is read from the native cache, not the 8-bit display. The viewer uses the source-plane affine and falls back to source-axis orientation labels where needed.

The 2D canvas uses physical aspect ratios from affine axis lengths. Non-axial rows are reversed for superior-up presentation when `affine_ras[2][2] > 0`; clicks apply the inverse row transform and overlays/orientation labels follow the display. Native PNG arrays and 3D texture UVs remain unchanged. This presentation does not resample or fully de-shear oblique grids. The optional 3D native-slice plane defaults off for overview/anatomy, with the 2D source panel still available.

Slice scrolling moves an existing selection along the active axis, discards stale HU/coordinates, and refetches them. Crosshairs appear only on the current slice; sequence guards ignore superseded voxel responses without claiming to eliminate every asynchronous race. Anatomy tour cameras fit requested layer bounds, separate from candidate-focused framing. Mobile control panels collapse while preserving access to the 2D source panel.

Dynamic cuts use dynamic lighting without baked shadows. Cuts are uncapped rendering boundaries, not organ interiors. Local tours expand minimal manifest stops with available-layer, source-slice, and candidate stops while preserving sufficiently complete tours without duplicate fallbacks. Interactive camera transitions depend on the current view. Blender is not a runtime or video dependency.

## Video Rendering

Install the optional video extra and browser in the activated environment, and provide `ffmpeg` with `libx264` on `PATH`:

```bash
uv pip install -e '.[video]'
python -m playwright install chromium
ct-edu render-video --workspace /path/to/external/new-workspace
```

The completed workspace and built frontend are required, but `serve` need not be running. Defaults are 20 seconds, 15 fps, width 1280, height 720, port 0 (available ephemeral port), and `tour.mp4` inside the workspace. `--output` can specify a new relative or absolute MP4 path under that workspace; the parent must exist. Symlinks, traversal, and existing output are rejected. Option limits: finite duration in `(0,120]` seconds, integer fps in `1..60`, even width/height at least 2 and at most 1920x1080, port `0..65535`. Frame count is `ceil(duration * fps)` and encoded duration is `frames / fps`.

The renderer starts a guarded loopback server and launches headless Playwright Chromium with a private temporary profile in a staging sibling of the workspace. Driver/browser temporary paths are external and debug logging is suppressed. Browser request routing allows only that exact loopback origin's GET/HEAD requests; other requests, WebSockets, and service workers are blocked. These are capture-browser controls, not OS-wide network isolation.

Capture waits for the viewer, fonts, and expected mesh count, then steps explicit frame times through a timed orbit and tour. With no annotations, it also sweeps native source slices; annotation tours retain their source selection. Full-viewport PNG screenshots include UI and educational warnings. Timing is explicit, but byte-identical rendering across browsers/platforms is not guaranteed.

PNG frames stream to ffmpeg for no-audio H.264 (`libx264`, `yuv420p`, CRF 20, faststart MP4). `-map_metadata -1` strips container metadata, not identifying content visible in images. Encoding occurs in private staging; successful output is published via an exclusive hard link preserving `0600` permissions. Staging and destination must share a filesystem supporting hard links. An output appearing during capture is not overwritten. Browser, server, encoder, and temporary profile/staging resources are cleaned up on completion or handled failure.

Success prints JSON containing `status: complete`, `frames`, `fps`, `duration`, `width`, and `height`, without an output path. Dependency, asset, browser, encoder, option, and publication failures produce fixed `E_VIDEO_*` codes; see [troubleshooting](../README.md#troubleshooting). Video generation does not upgrade mask fidelity, establish a diagnosis, or authorize publication of study material.
