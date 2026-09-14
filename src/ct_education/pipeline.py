"""External build transaction and the version-one viewer contract."""

import itertools
import mmap
import os
from pathlib import Path
import tempfile

import numpy as np

from .dicom import Collection, decode_hu
from .safety import PipelineError, boundaries, directory_fd, disjoint, local_file, read_json, write_json
from .segmentation import LAYER_INFO, mesh_for_mask, segment


def ras_bounds(shape, affine_ras):
    corners = np.array(list(itertools.product(*[(-0.5, size - 0.5) for size in shape[::-1]])))
    points = corners @ affine_ras[:3, :3].T + affine_ras[:3, 3]
    return {"min": points.min(axis=0).tolist(), "max": points.max(axis=0).tolist()}


def annotations_from_file(path, shape, affine_ras):
    if path is None:
        return []
    boundaries(annotations=path)
    path = Path(path).expanduser().resolve(strict=True)
    raw = read_json(path.parent, path.name)
    if not isinstance(raw, list) or len(raw) > 100:
        raise PipelineError("E_ANNOTATIONS")
    annotations = []
    seen = set()
    inverse = np.linalg.inv(affine_ras)
    try:
        for item in raw:
            if not isinstance(item, dict) or set(item) - {"id", "label", "position_ras", "radius_mm", "description", "review_status"}:
                raise ValueError
            if not isinstance(item["position_ras"], list) or any(type(value) not in (int, float) for value in item["position_ras"]) or type(item["radius_mm"]) not in (int, float):
                raise ValueError
            position = np.asarray(item["position_ras"], dtype=float)
            radius = float(item["radius_mm"])
            if position.shape != (3,) or not np.isfinite(position).all() or not np.isfinite(radius) or not 0 < radius <= 100:
                raise ValueError
            ijk = (inverse @ np.r_[position, 1])[:3]
            if (ijk < -0.5).any() or (ijk > np.asarray(shape)[::-1] - 0.5).any():
                raise ValueError
            identifier = item["id"]
            if not isinstance(identifier, str) or not identifier.isascii() or not identifier.replace("-", "").replace("_", "").isalnum() or len(identifier) > 64 or identifier in seen:
                raise ValueError
            seen.add(identifier)
            # Free text may contain PHI. Never copy caller text into served output.
            annotations.append({
                "id": f"candidate-{len(annotations) + 1}", "label": f"Candidate {len(annotations) + 1}",
                "position_ras": position.tolist(), "radius_mm": radius,
                "description": "Externally supplied position and radius; this sphere is not a segmented lesion.",
                "review_status": "unverified candidate",
            })
    except (KeyError, TypeError, ValueError, OverflowError):
        raise PipelineError("E_ANNOTATIONS") from None
    return annotations


def build(source, workspace, series_number=None, annotations=None):
    original_source, original_workspace = source, workspace
    _, source, workspace = boundaries(source=source, workspace=workspace, annotations=annotations)
    if workspace.exists() or workspace.is_symlink():
        raise PipelineError("E_WORKSPACE_EXISTS")
    if not workspace.parent.is_dir():
        raise PipelineError("E_WORKSPACE_PARENT_REQUIRED")
    with Collection(source) as collection:
        stack = collection.select(series_number)
        if np.prod(stack.shape, dtype=np.int64) > 600_000_000:
            raise PipelineError("E_VOLUME_SIZE")
        affine_ras = np.diag([-1, -1, 1, 1]) @ stack.affine
        imported = annotations_from_file(annotations, stack.shape, affine_ras)
        # A private sibling is never served. Manifest publication is the final commit marker.
        with directory_fd(workspace.parent) as parent_fd:
            with tempfile.TemporaryDirectory(prefix=".ct-edu-stage-", dir=workspace.parent) as staging:
                stage = Path(staging)
                disjoint(source, stage)
                initial_identity = os.stat(stage)

                def check():
                    checked = boundaries(source=original_source, workspace=original_workspace, annotations=annotations)
                    if checked[1:] != [source, workspace]:
                        raise PipelineError("E_PATH_CHANGED")
                    if not os.path.samestat(os.stat(workspace.parent), os.fstat(parent_fd)):
                        raise PipelineError("E_PATH_CHANGED")
                    if stage.is_symlink() or not os.path.samestat(os.stat(stage), initial_identity):
                        raise PipelineError("E_PATH_CHANGED")

                check()
                with local_file(stage, "volume.npy", "w+b") as stream:
                    np.lib.format.write_array_header_2_0(stream, {
                        "descr": np.dtype(np.float32).str, "fortran_order": False, "shape": stack.shape,
                    })
                    offset = stream.tell()
                    stream.truncate(offset + int(np.prod(stack.shape)) * 4)
                    stream.flush()
                    with mmap.mmap(stream.fileno(), 0) as mapped:
                        volume = np.ndarray(stack.shape, dtype=np.float32, buffer=mapped, offset=offset)
                        for k, frame in enumerate(stack.frames):
                            check()
                            volume[k] = decode_hu(collection, frame)
                        masks, label_affine, stride, messages = segment(volume, stack.affine)
                        del volume
                        mapped.flush()
                check()
                labels = np.zeros(next(iter(masks.values())).shape, dtype=np.uint8)
                layers = []
                with directory_fd(stage) as stage_fd:
                    os.mkdir("meshes", 0o700, dir_fd=stage_fd)
                for index, (name, mask) in enumerate(masks.items(), 1):
                    labels[mask] |= 1 << (index - 1)
                    mesh = mesh_for_mask(mask, label_affine, stack.shape, stride)
                    if mesh is None:
                        if mask.any():
                            messages.append(f"{name}: surface omitted because extraction was unsupported or exceeded the mesh budget.")
                        continue
                    check()
                    write_json(stage, f"meshes/{name}.json", mesh)
                    title, color, description = LAYER_INFO[name]
                    layers.append({"id": name, "name": title, "color": color, "description": description,
                                   "review_status": "algorithmic candidate", "mesh": f"meshes/{name}.json"})
                check()
                with local_file(stage, "labels.npy", "wb") as stream:
                    np.save(stream, labels, allow_pickle=False)
                check()
                write_json(stage, "labels-grid.json", {
                    "shape": list(labels.shape), "affine_lps": label_affine.tolist(),
                    "stride_kji": stride.tolist(), "encoding": "bitfield",
                    "bits": {name: 1 << index for index, name in enumerate(LAYER_INFO)},
                })
                check()
                write_json(stage, "provenance.json", {
                    "schema_version": 1,
                    "series_uid": str(stack.frames[0].header.SeriesInstanceUID),
                    "frames": [{"member": frame.member, "sop_uid": str(getattr(frame.header, "SOPInstanceUID", ""))} for frame in stack.frames],
                    "annotation_source_supplied": annotations is not None,
                    "algorithm": "cpu-threshold-v1", "label_grid": "labels-grid.json",
                })
                if annotations is not None:
                    messages.append("Annotation identifiers and free text were replaced with generic text to prevent disclosure.")
                center = (affine_ras @ np.r_[(np.asarray(stack.shape)[::-1] - 1) / 2, 1])[:3].tolist()
                tour = [{"id": "overview", "title": "Source-linked overview",
                         "description": "Compare candidate surfaces with native HU slices; these are not clinical labels.",
                         "layer_ids": [layer["id"] for layer in layers], "target_ras": center}]
                for item in imported:
                    tour.append({"id": "tour-" + item["id"], "title": item["label"],
                                 "description": item["description"], "layer_ids": [layer["id"] for layer in layers],
                                 "target_ras": item["position_ras"], "annotation_id": item["id"]})
                manifest = {
                    "schema_version": 1, "shape": list(stack.shape), "spacing": stack.spacing.tolist(),
                    "affine_lps": stack.affine.tolist(), "affine_ras": affine_ras.tolist(),
                    "bounds_ras": ras_bounds(stack.shape, affine_ras), "layers": layers, "annotations": imported,
                    "warnings": messages, "source": {"modality": "CT", "slice_count": len(stack.frames)}, "tour": tour,
                }
                check()
                write_json(stage, "manifest.json", manifest)
                check()
                # Exclusive mkdir prevents overwrite, even if a second builder won the race.
                os.mkdir(workspace.name, 0o700, dir_fd=parent_fd)
                with directory_fd(workspace) as destination_fd, directory_fd(stage) as stage_fd:
                    for name in ("volume.npy", "labels.npy", "labels-grid.json", "provenance.json", "meshes", "manifest.json"):
                        check()
                        if not os.path.samestat(os.stat(workspace), os.fstat(destination_fd)):
                            raise PipelineError("E_PATH_CHANGED")
                        os.rename(name, name, src_dir_fd=stage_fd, dst_dir_fd=destination_fd)
                return manifest
