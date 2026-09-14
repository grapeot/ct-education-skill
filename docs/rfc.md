# Technical Architecture

**Status: proposed contract, not implemented.** The planned CLI verbs are `inspect`, `build`, `serve`, and optional `render-video`; command syntax is not finalized. `inspect` would validate paths and inventory independent series, `build` would generate external assets, and `serve` would expose a guarded local viewer. Video remains downstream.

## Source Truth and Geometry

Raw pixel values convert to Hounsfield Units through `HU = pixel_value * RescaleSlope + RescaleIntercept`, respecting signed pixel representation and per-frame rescale values. Validate CT modality and supported intensity transforms; reject unsupported encodings rather than silently treating display pixels as HU.

Per-series source HU, affine or per-frame geometry, and voxel labelmaps are authoritative computational data. Labelmaps are not clinical ground truth. Meshes are disposable rendering derivatives; smoothing or decimation must not modify source voxels or labels.

Never stack distinct series or sort by filename or `InstanceNumber` alone. Derive the slice normal from `cross(IOP[0:3], IOP[3:6])`, where IOP is `ImageOrientationPatient`, and sort by projecting IPP (`ImagePositionPatient`) onto that normal. Preserve obliquity and independent reconstruction grids. Reject irregular stacks in v1, including duplicate positions, gaps, nonuniform spacing, changing orientation, or unsupported multiframe objects. Do not invent a uniform affine.

Array order is `[k, j, i]`, with 0-based voxel centers: `i` is column, `j` is row, and `k` is the sorted frame. Array axes are not necessarily physical x/y/z axes. Native LPS (left, posterior, superior) millimeters follow:

```text
P_LPS = IPP[k]
      + i * PixelSpacing[1] * IOP[0:3]
      + j * PixelSpacing[0] * IOP[3:6]
```

For a validated uniform stack, the affine maps `[i,j,k,1]` to LPS; its slice column uses the actual adjacent IPP displacement, never `SliceThickness`. Preserve source-frame lookup in the private workspace.

The proposed viewer uses RAS (right, anterior, superior) millimeters:

```text
lps_to_viewer = diag(-1, -1, 1)
P_viewer = lps_to_viewer * P_LPS
viewer_to_lps = diag(-1, -1, 1)
```

Name and preserve these transforms and their inverses. A mesh hit is a continuous position, not necessarily a voxel center. Map it through viewer-to-LPS and inverse source geometry, show fractional source coordinates, then select the nearest in-bounds voxel center and its original frame. State the rounding rule and reject out-of-bounds selections rather than silently clamping. Show the native slice separately from interpolated displays. Physical locations establish geometry, not diagnostic evidence.

## Filesystem and Privacy Contract

Repository root, external input root, and external output workspace must be pairwise disjoint: no equality or ancestor/descendant relationship in either direction. Resolve canonical real paths before study reads or output writes, including symlinks and non-existent leaves via existing ancestors. Reject data paths resolving into or through the repository. Input is read-only to the tool.

Recheck before every write; prohibit workspace symlinks that escape the allowed root. Later implementation must address path replacement between checking and opening, not rely on string prefixes alone. Output overwrite behavior must be explicit and non-destructive by default. Any failed boundary or geometry check stops the affected build with a generic error code, not a raw path or header dump.

No medical assets ever enter the repository, public app assets, remote services, docs, examples, logs, or CI. Derivatives are private too. Private aliases, source-file lookup, and local workspace mappings live only in caller-owned private configuration or external storage. Logs use aggregate counts and error codes, not patient identifiers, filenames, paths, or raw exceptions.

Ignore rules cover sensitive directory names at any depth and medical/binary suffixes. They are defense in depth, not proof of privacy; the manual gate in [AGENTS.md](../AGENTS.md) applies before every PR.

## External Outputs

These are proposed deliverables, not a shipped schema or fixed binary format:

- `manifest.json`: schema version, opaque local series key, grid shape/order, HU conversion, source geometry, viewer transform, algorithm parameters/versions, warnings, and review status. No raw identifying headers or fabricated confidence probabilities.
- Source HU volume and voxel labelmaps, preserving the source grid or an explicitly recorded derived-grid transform.
- Disposable surface meshes linked to source labels and geometry.
- `tour.json`: deterministic stops with source coordinates, layer visibility, camera targets, and local educational text.
- Optional video, generated downstream in the same external privacy boundary.

Reviewed-label imports must validate shape, affine, coordinate convention, series association, and provenance. Do not silently resample or align incompatible labels. Preserve method and review status separately. No manifest or source mapping is a public demo asset.

## Local Viewer

Bind to loopback `127.0.0.1` by default; no remote publish, reverse proxy, tunnel, or non-loopback option in v1. Guarded routes expose only allowlisted workspace files needed for viewing, including HU slice data and labels. Never expose the repository tree, source DICOM directory, arbitrary filesystem paths, or private source lookup. Generic frontend code may be served through explicit application routes, never a repository directory listing.

Require traversal/symlink rejection and loopback host/origin validation; loopback binding alone is not a complete access-control boundary. Study responses must not enter persistent browser caches or service-worker bundles. No telemetry, CDN fetches, or cloud-generated tours.

Dynamic cuts use dynamic lighting or unlit caps, without baked static shadows that would contradict moving geometry. Blender is optional downstream for presentation and video; it is neither a source of truth nor an MVP dependency.
