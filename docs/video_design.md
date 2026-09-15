# Blender Educational Film Design

## 1. Decision and Status

Make a finished offline film with a Blender-rendered 3D scene on the left and the corresponding source CT image on the right. Start with the image, build spatial understanding, then return to the image as evidence. The existing browser `render-video` remains a separate demonstration product, not the production renderer.

This is the updated design-first checkpoint: the 36-second timing and motion refinements below are implementation-pending. `render-cinematic` is proposed here; implementation and measured results are recorded separately in [working.md](working.md). This document describes the target film, not a claim that every shot has shipped. The coordinating maintainer must privacy-review and commit/PR this design before implementation.

The acceptance question: can a viewer explain how the visible plane relates to the source image, distinguish display surfaces from image evidence, and understand size without mistaking a locator for a segmented finding?

Execution gates, in order:
1. This design and scientific contract.
2. Representative hero frames for shading, orientation, clipping, and scale.
3. A 4-7.5 second motion proof at final cadence for easing, rhythm, and synchronization.
4. A full example 36-second film only if the measured render budget permits.

First-screen recap: the film is independent of the browser demonstration. Both pictures must describe the same place at the same time. Prove that relationship in a short render before producing the long film.

## 2. Sequence Rationale

The principal sequence is source image, reconstructed spatial context, structure, plane correspondence, then local evidence. An opening beauty orbit was considered and rejected: it would teach the derived surface before establishing what actually supports it.

Native axial images are reconstructed from X-ray projections. Stacking representative images is a teaching model of a sampled volume, not a literal animation of scanner acquisition. No projection beams, detector-row pulses, breathing, heartbeat, or invented tissue movements are needed.

The single full turn establishes spatial confidence with a rhythmic, dance-like fast-slow-fast camera rotation, not uniform doubled angular speed. Later camera movements answer specific questions rather than continuing a uniform spinner. Acceleration creates momentum, braking directs attention, and settled holds give viewers time to read. Deliberate CT sweeps may remain steady; source images, labels, and rulers do not dance, bounce, or overshoot.

Display separation is allowed only when explicitly labeled. It changes mesh or plane presentation transforms, never source sampling coordinates. Every separated component returns to its stored rest transform.

## 3. Shared Geometry and Image State

Both panels are driven by one per-frame state. A plane is not independently recreated by the left renderer and right compositor.

### Coordinate Mappings

- Patient space is Right-Anterior-Superior (RAS) millimeters.
- Native arrays use `[k,j,i]`; the source affine maps homogeneous `[i,j,k,1]` to RAS millimeters.
- Reduced labels have their own affine and shape. Matching native and label indices is invalid.
- Blender uses Z-up meters: `world_xyz = 0.001 * (ras_xyz - stored_center_ras)`.
- The axes remain RAS-aligned, with no hidden permutation or sign flip. The center translation is persisted externally.
- A plane stores origin, screen-right unit vector `u`, screen-up unit vector `v`, and `normal = normalize(cross(u,v))`.
- For a sheared grid, store the full pixel basis as well as unit vectors. A scale along one axis must not imply a globally orthogonal grid.

### Per-Frame State

Persist plane origin/basis/normal, native source affine, label affine, selected source index, crop, window center/width, physical pixel basis, image identity, and dimensions. Also persist camera basis/projection/framing, visibility, colors, and display offsets.

The identical windowed HU image and mapping feed both the exposed left plane and right panel. The right image is not a separately selected approximation. Source HU and label arrays remain read-only.

An exposed cut face uses HU texture clipped to a body footprint. A colored mesh boundary is not a CT interior. Dynamic shader clipping is preferred to repeated heavy Boolean evaluation; it may leave uncapped mesh boundaries, with the HU plane supplying image evidence rather than fabricated tissue.

The body footprint is a display mask, not a reviewed body segmentation. It must not erase peripheral image evidence without disclosure. The right panel may retain the full source image background while sharing the identical underlying HU image.

### Face-On Proof

Derive the camera from the actual screen-right and screen-up basis. Looking down the head-foot axis blindly can mirror the source image. In an orthographic proof hold, both panels must match orientation, crop, physical aspect, and apparent framing.

Use an asymmetric synthetic phantom to verify handedness. For tilted or sheared data, either explicitly support the full mapping or reject the proof mode; do not silently call a source-grid section an anatomical world-axis reformat.

Return to perspective only after the matching hold. Do not interpolate projection modes as if their scales were interchangeable.

## 4. Simultaneous Millimeter References

Both panels carry readable physical references during slicing and local inspection. Millimeters come from the affine, not a fixed decorative pixel bar.

- Right CT: derive pixels per millimeter from the actual image pixel basis, crop extent, and final resized image rectangle. Letterboxing is outside that rectangle.
- Left perspective: place ruler endpoints in the active plane, transform from RAS to Blender, and project through that frame's camera. Label the reference as applying in the slice plane.
- Left orthographic: derive scale from camera field width and output rectangle. Match the right crop for the face-on proof.
- Zoom: regenerate both references every frame, choosing readable 1/2/5-series millimeter lengths rather than adding excessive decimal precision.
- Overview: use an attached plane reference or landmark marker, not a claimed global perspective measurement.
- Orientation: derive R/L, A/P, S/I or explicit source-axis labels from the screen basis; never paste fixed orientation labels across camera changes.
- Locator: a sphere or ring marks a candidate location. Its radius is a display parameter, not a measured lesion diameter or a segmented surface.

There is currently no reliable candidate mesh in the source contract. Local inspection therefore uses the location marker and real CT close-up. Independently verified segmentation can be added later; no synthetic nodule beauty mesh or smoothing of a tiny candidate substitutes for it.

## 5. Example Storyboard: 36 Seconds

The requested 100% speed increase means 2x playback speed: the original 72-second cut becomes exactly 36 seconds. All original shot boundaries, holds, and transitions are nominally halved first. The windows below are fixed for this principal cut; authored motion curves redistribute movement and reading time inside each window, never add time or extend a shot. Transitions consume their allocated windows, not extra handles. Missing candidate layers are omitted with truthful captions rather than fabricated.

### Shot 1, 0-3: Native Axial Image

- Learning: an axial CT image is reconstructed from projections.
- Left: one source-textured plane, initially face-on in quiet space.
- Right: the same windowed native axial image, without browser chrome.
- Motion: a one-second reading hold, followed by a deliberate tilt revealing the plane within the remaining two seconds.
- Scale: simultaneous affine-derived rulers; the left ruler stays attached to the plane as perspective begins.

### Shot 2, 3-6.5: Images Into Spatial Context

- Learning: a sampled image volume provides depth; the illustrative stack is not acquisition footage.
- Left: a small representative subset appears with labeled exaggerated gaps, then returns to true source positions before surfaces are revealed.
- Right: source images follow the selected stack plane, with a restrained position indicator.
- Motion: staged, individually offset plane entries with gentle braking, then a return to rest and surface reveal inside 3.5 seconds. Correct the prior cut's simultaneous stack appearance; do not reveal all planes on the first frame. No stretching of anatomy.
- Scale: both selected-plane rulers remain physical; exaggerated spacing is explicitly labeled and not presented as anatomical separation.

### Shot 3, 6.5-11.5: One Confident Turn

- Learning: see the spatial relationship of available structures from all sides.
- Left: a single 360-degree camera orbit around source-derived surfaces.
- Right: retain a named axial source image, not an invented rotating scout.
- Motion: an early quick arc, a calm front/three-quarter reading beat, a second quick arc, then deceleration into a settled hold. Use the normalized profile below within these five seconds, not a uniform 2x spinner.
- Scale: attached selected-plane marker on the left and corresponding physical ruler on the right; no global screen-space bar.

### Shot 4, 11.5-14.5: Bone, Then Reduced Context

- Learning: the dense-structure candidate helps establish the cage and central support.
- Left: porcelain bone gains emphasis; surrounding context fades gently rather than deforming.
- Right: the selected source image changes to a disclosed bone-oriented display window.
- Motion: a small lateral camera move followed by a hold.
- Scale: active-plane references in both panels; no inferred vertebral measurements.

### Shot 5, 14.5-18: Airspaces and Branch Candidates

- Learning: the airspace envelope is not a hollow lung; airway and dense vascular candidates are incomplete heuristic results.
- Left: muted teal envelope recedes to reveal available branch candidates in distinct restrained colors. Correct the prior cut's overly dark branch emphasis with controlled light, contrast, and envelope opacity so existing branches remain visible; this is a pending design correction, not an implemented result or a reason to invent missing branches.
- Right: a corresponding source-grid section in lung window, not a maximum-intensity projection.
- Motion: a slow inspection arc, with anatomy fixed at rest.
- Scale: plane-local rulers in both panels; no branch-caliber claims from smoothed meshes.

### Shot 6, 18-24: Three Synchronized Sweeps

- Learning: axial, coronal, and sagittal source-grid sections describe the same volume from different directions.
- Left: each active plane traverses the volume, with the same HU texture exposed at the cut.
- Right: the identical image changes with the plane, with explicit axis/orientation labels.
- Motion: allocate two seconds per axis, including a 0.5-second settled stop and the editorial axis change. The traversal may be slow and deliberate relative to the hero arcs, with a steady interior and smooth start/braking; do not impose dance-like speed pulses on CT sampling.
- Scale: simultaneous depth-qualified left and image-derived right millimeter rulers, recalculated per frame.

### Shot 7, 24-28: The Two Pictures Agree

- Learning: looking directly at the 3D plane produces the source image, not a different anatomical illustration.
- Left: context above the plane retires by clipping/fade; remaining context clears, then camera approaches the plane normal.
- Right: lock the selected image and its crop.
- Motion: clear context and brake into an orthographic face-on match during 24-26 seconds; hold both panels and rulers still during 26-28 seconds to compare asymmetric features.
- Scale: identical physical crop/framing and ruler length in both panels. This is screen-scale parity, not physical life-size on every display.

### Shot 8, 28-33: Location, Then Local Evidence

- Learning: distinguish the location in whole-volume context from magnified source detail.
- Left: marker at unchanged patient coordinates; move into orthographic local plane inspection, not a fabricated lesion surface.
- Right: first the wider image, then the same region cropped around the externally supplied candidate.
- Motion: wide hold at 28-28.5 seconds, eased coordinated zoom at 28.5-30 seconds, then a stable close-up and ruler-reading hold at 30-33 seconds. No overshoot or extra dwell outside the shot.
- Scale: both bars update through the zoom; use readable rounded millimeters. Caption: locator only, not a segmented lesion.

### Shot 9, 33-36: Return to Overview

- Learning: retain the relationship between local evidence and spatial context, with uncertainty intact.
- Left: return to rest-pose overview and the established principal angle.
- Right: restore the wider source image at the selected location.
- Motion: smooth pullback during 33-35 seconds and a settled closing hold during 35-36 seconds, not another orbit.
- Scale: attached reference on the left and wider image ruler on the right; no global perspective measurement claim.

### Normalized Orbit Profile

For Shot 3, let `u = (t - 6.5) / 5` and animate an unwrapped camera azimuth from 0 to 360 degrees. Choose the starting azimuth so the calm 130-155-degree interval frames the front/three-quarter reading view; this is a camera offset, not a change to patient axes or geometry. The concrete knots below specify angle and angular velocity in degrees per unit `u` (divide velocity by five for degrees per second).

| Local time `u` | Unwrapped angle | Velocity `d(angle)/du` | Purpose |
|---|---|---|---|
| 0.00 | 0 | 0 | Smooth departure |
| 0.20 | 130 | 60 | Early quick arc has braked |
| 0.55 | 155 | 60 | Calm reading beat ends |
| 0.80 | 335 | 500 | Second quick arc is braking into final deceleration |
| 0.90 | 360 | 0 | Settle at the principal angle |
| 1.00 | 360 | 0 | Final 0.5-second hold ends |

Use monotone cubic Hermite interpolation with these shared knot velocities for C1 continuity, including the constant final hold. Do not use independent ease-in/ease-out segments that stop at every knot. A C2 alternative is acceptable only if it preserves monotonicity, reading beats, endpoints, and the five-second allocation. Animate the unwrapped scalar angle or an equivalent explicit orbit path; interpolating only quaternion endpoints at 0 and 360 degrees can select the zero-length shortest path. Other camera and display transitions must likewise maintain at least C1 continuity except at intentional editorial cuts. Geometry, rest transforms, slice positions, and the spatial sampling method remain unchanged.

## 6. Art Direction

Use charcoal/navy negative space, matte porcelain bone, muted teal airspace, a separate warm branch color, and amber only for the locator. Soft key and rim lights should define existing surfaces without glossy plastic glare. Avoid procedural surface noise that implies invented anatomy.

Aim for a focused, refined Blender film through framing, lighting, and motion, not photoreal synthetic anatomy. Disable motion blur on scientific imagery, exposed HU planes, scale panels, and labels; fast camera arcs must not smear image evidence or measurements.

Keep fixed two-panel framing, restrained chapter numbers, generous image area, and concise captions. No controls, simulated cursor, OS decorations, or dashboard panels. Light and color explain spatial depth; image evidence remains neutral grayscale. Uncertainty stays visible without covering the images.

## 7. Production and Validation

The proposed additive command drives a generic deterministic Blender script. It must emit an external packed `master.blend`, versioned PNG sequence, MP4, per-frame state, benchmark, and validation record. The script plus state is the authoritative motion source; a saved hero scene alone does not encode the whole film.

Use [RFC source geometry](rfc.md#source-truth-and-geometry), [external artifacts](rfc.md#external-artifacts), and [privacy boundaries](rfc.md#filesystem-and-privacy). This opt-in offline pipeline must explicitly validate its separate external output root; the browser renderer's existing workspace-contained output rule is unchanged.

The primary target is 24 fps, matching the prior renderer cadence: exactly 864 frames for 36 seconds, with zero-based output indices 0-863 and the end boundary at 864. Shot boundary frame indices are 0, 72, 156, 276, 348, 432, 576, 672, 792, and 864. A separately selected 30 fps variant would require 1080 frames, not a longer cut. Desired delivery is 1920x1080, subject to measured render budget; 1280x720 is an optional preview, not an unannounced final-quality substitution.

Start with bounded EEVEE hero renders and a 4-7.5 second low-resolution proof at final cadence. Set a render timeout and estimate total cost from measured frames. Do not launch unattended 4K or long Cycles jobs. Interrupted sequences remain versioned and recoverable; changed settings require a new version.

Implementation must first map the raw 72-second timeline to 36 seconds with `t_raw = 2 * t_output`, halving nominal holds and transitions as well as shot boundaries. Then apply authored, monotone nondecreasing local time warps to the relevant motion tracks inside each fixed shot, with endpoints pinned and explicit plateaus for holds. This is not a second global speed multiplier. Deliberate scan tracks may retain steady timing; whenever a selected plane changes, both panels consume the same resulting state. Retiming changes temporal scheduling, not source geometry, slice sampling rules, or rest coordinates.

The coordinating implementation must test the 36-second duration and boundary frames, monotone warps, angle/velocity continuity, full unwrapped turn, fast-slow-fast contrast, and exact hold intervals. It must also verify staged stack entry, branch visibility after context recedes, stable labels, synchronized source-image pairs, and ruler readability during proof and local detail. These checks and visual results are pending; this document-only update performs no implementation or renders.

Validate exact expected frame indices, open every PNG and check dimensions, probe frame rate/duration/codec, and fully decode the MP4 with ffmpeg. Numerical trajectory tests and frame comparisons supplement actual continuous playback; snapshots do not establish motion quality.

Private source paths, coordinates, images, logs, and provenance remain external. Public failures contain fixed codes, not raw exceptions. No frontend, server route, live media selection, deployment, or Git mutation belongs to this workflow. A future web preview must select one allowlisted film rather than expose an output directory.
