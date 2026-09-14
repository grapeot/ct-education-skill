---
name: ct-education
description: Plan and develop local educational 3D chest CT exploration with source-slice proof, algorithmic candidate layers, and external-only private workspaces. Scaffold specification, not an implemented CLI.
---

# CT Education Skill

## Goal and Status

Guide development and eventual local use of interactive educational chest CT exploration: lung, airway, and vessel candidates linked to original slices and source coordinates, with a local guided tour. **Scaffold only:** no CLI, parser, segmentation, viewer, server, or video implementation exists. `inspect`, `build`, `serve`, and optional `render-video` are proposed verbs, not runnable commands.

Type: Workflow / Specification. Output location: external private workspace only. Created: 2026-09-14. Expose only this root skill to workspace discovery.

## Boundaries

- Education only, never diagnosis, clinical advice, or treatment planning. Noncontrast data does not justify complete vasculature or reliable artery-vein segmentation claims.
- CPU v1 plans thresholds, chest masks, connected components, and seeded region growing. Label outputs as algorithmic candidates and disclose leakage, missing structures, and uncertainty. Do not invent calibrated probabilities.
- Reviewed label imports require grid and provenance validation; review is not automatic ground truth. No high-quality learned segmentation promises without a supplied, licensed, and evaluated model.
- DICOM input is externally supplied and read-only. Resolve real paths before study IO; repository, input root, and workspace must be pairwise disjoint, including equality and ancestor relationships. Recheck writes and reject escaping output symlinks.
- No medical assets or identifying facts in repository files, public app assets, docs, examples, logs, CI, or remote tools. All derivatives stay external. Synthetic fixtures are generated at test time only, outside the repository.
- Private aliases and source mappings belong in the caller's private configuration, not this skill. Never look for private health records to fill documentation gaps.
- Planned serving defaults to `127.0.0.1`, with no remote publish or non-loopback option. Tours are local. Blender and video are optional downstream; no baked static shadows for dynamic cuts.

## Resources

- [Overview and installation](../README.md)
- [Contributor rules and mandatory PR privacy gate](../AGENTS.md)
- [Product requirements and phases](../docs/prd.md)
- [Geometry, path safety, and output contract](../docs/rfc.md)
- [Current checks and future QA](../docs/test.md)
- [Working status](../docs/working.md)

Use repository docs and authorized local tools; no runtime tools ship yet. Preserve native source HU, affine/per-frame geometry, and voxel labelmaps as computational truth. Meshes are disposable derivatives. Keep independent DICOM series separate; IPP/IOP determine geometry, not filenames. Follow the RFC's 0-based `[k,j,i]` indexing and explicit LPS-to-viewer transform.

## Proposed External Outputs

The workspace will contain a versioned `manifest.json`, source HU volume, voxel labelmaps, derivative meshes, and coordinate-linked `tour.json`. Optional video remains external too. The manifest records an opaque series key, grid/order, source geometry, HU conversion, transforms, method/parameters/versions, warnings, and review status, not raw identifying headers. Formats are proposed, not shipped schemas. No output manifest is a public demo asset.

## Acceptance

For the current scaffold, offline `python -B -m unittest discover -s tests -v` must pass in an activated uv-managed environment, only this root skill may exist, and every PR must pass manual privacy review. Update the dated working log with actual outcomes.

Future implementation acceptance requires tests that reject overlapping roots and escaping symlinks before study IO, preserve independent native series geometry, and roundtrip known synthetic source coordinates through viewer transforms. Clicks must identify the original frame and bounded source coordinates, with interpolation clearly distinguished. Users must see method/review status and uncertainty for every candidate layer. Tour stops must reproduce source-coordinate selections without network access. The viewer must keep all study material external to public app assets.

## Stop Rules

Missing tools, authorized input, or an external workspace are blockers, not permission to fabricate results. Reject unsupported or ambiguous geometry rather than inventing an affine. Never upload study data or raw errors to remote LLMs or issue trackers. Stop a PR on unresolved privacy findings and report only generic error codes or missing capabilities.
