# CT Education Skill

CT Education Skill specifies a local educational 3D chest computed tomography (CT) exploration tool. **Status: scaffold only.** No CLI, DICOM parser, segmentation pipeline, viewer, server, or video exporter is implemented.

The planned tool is for anatomy education and technical exploration, not medical diagnosis, clinical advice, or treatment planning.

## Planned Features

- Local interactive 3D chest CT with togglable lung, airway, and vessel candidate layers.
- Dynamic cut planes with dynamic lighting or unlit cut caps, without baked static shadows.
- Slice proof: a 3D selection links to native source slices, 0-based voxel indices, and physical coordinates.
- A deterministic local guided tour driven by source coordinates and camera targets.

The CPU baseline will use thresholds, chest masks, connected components, and seeded region growing. These produce algorithmic candidates, not confirmed anatomy. Reviewed label imports are planned. No high-quality learned segmentation is promised without a supplied and evaluated model. Noncontrast scans cannot support promises of complete vasculature or reliable artery-vein separation.

## Data Requirements

Input DICOM must stay outside the repository and be read-only to the tool. Outputs must go to an external workspace. The repository, input root, and output workspace must be pairwise disjoint after resolving real paths: none may equal, contain, or sit inside another.

Studies and their derivatives, including meshes, screenshots, tours, and video, must remain outside the repository and public application assets. The planned server binds to loopback `127.0.0.1` only, with no remote publishing, telemetry, or cloud tour service.

The fake configuration in [`.env.example`](.env.example) uses `CT_EDU_WORKSPACE=/path/to/external/workspace`. It is a proposed setting, not consumed by any implementation yet. Proposed future CLI verbs are `inspect`, `build`, `serve`, and optional `render-video`; syntax and flags are not finalized.

## Skill Installation

This repository provides a Markdown skill specification, not a runnable application. Give its eventual GitHub URL or local checkout to Codex, Claude Code, Cursor, OpenCode, or another coding agent and ask it to install the skill.

The installer should read the target workspace's `AGENTS.md` or `CLAUDE.md`, then routing files such as `WORKSPACE.md`. Register exactly one root skill, [`skills/ct_education.md`](skills/ct_education.md), in `rules/skills/INDEX.md` or `skills/INDEX.md`. If neither index exists, add a short pointer in `AGENTS.md` or `CLAUDE.md`. Private workspace mappings remain in the caller's private configuration.

## Documentation

- [Product requirements](docs/prd.md)
- [Technical architecture](docs/rfc.md)
- [Test plan and current checks](docs/test.md)
- [Working status](docs/working.md)
- [Contributor rules](AGENTS.md)

## License

[MIT](LICENSE). Copyright 2026 CT Education Skill contributors.
