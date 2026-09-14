"""Header inventory, strict uniform-stack geometry, and per-slice HU decoding."""

from contextlib import ExitStack
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import quote
import warnings
import zipfile

import numpy as np
import pydicom
from pydicom.errors import InvalidDicomError
from pydicom.uid import CTImageStorage

from .safety import PipelineError, boundaries, local_file


TAGS = [
    "SOPClassUID", "SOPInstanceUID", "StudyInstanceUID", "SeriesInstanceUID",
    "FrameOfReferenceUID", "SeriesNumber", "Modality", "ImageType",
    "Rows", "Columns", "ImageOrientationPatient", "ImagePositionPatient",
    "PixelSpacing", "NumberOfFrames", "SamplesPerPixel", "PhotometricInterpretation",
    "RescaleSlope", "RescaleIntercept", "RescaleType", "ModalityLUTSequence",
    "RealWorldValueMappingSequence", "BitsAllocated", "BitsStored", "HighBit", "PixelRepresentation",
]


@dataclass
class Frame:
    member: str
    header: object


@dataclass
class Stack:
    frames: list
    affine: np.ndarray
    shape: tuple

    @property
    def spacing(self):
        return np.linalg.norm(self.affine[:3, :3], axis=0)[::-1]


class Collection:
    def __init__(self, source):
        boundaries(source=source)
        self.source = Path(source).expanduser().resolve(strict=True)
        self.resources = ExitStack()
        self.members = {}
        self.skipped = 0

    def __enter__(self):
        try:
            is_directory = self.source.is_dir()
            self.file_root = self.source if is_directory else self.source.parent
            if is_directory:
                files_to_scan = []
                for parent, dirs, files in os.walk(self.source, followlinks=False):
                    if any((Path(parent) / name).is_symlink() for name in dirs + files):
                        raise PipelineError("E_INPUT_SYMLINK")
                    files_to_scan.extend((Path(parent) / name).relative_to(self.source).as_posix() for name in files)
            else:
                files_to_scan = [self.source.name]
            for filename in sorted(files_to_scan):
                if is_directory and Path(filename).suffix.lower() != ".zip":
                    self.members["file:" + filename] = (None, filename)
                    continue
                boundaries(source=self.source)
                stream = self.resources.enter_context(local_file(self.file_root, filename))
                archive = self.resources.enter_context(zipfile.ZipFile(stream))
                seen_names = set()
                for item in archive.infolist():
                    name = item.filename
                    if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                        raise PipelineError("E_ZIP_MEMBER_PATH")
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise PipelineError("E_INPUT_SYMLINK")
                    if name in seen_names:
                        raise PipelineError("E_ZIP_DUPLICATE_MEMBER")
                    seen_names.add(name)
                    if item.is_dir():
                        continue
                    if item.file_size > 512 * 1024 * 1024:
                        raise PipelineError("E_ZIP_MEMBER_SIZE")
                    # Qualify private source lookup without extracting or conflating package names.
                    member = f"zip:{quote(filename, safe='/')}!/{quote(name, safe='/')}"
                    self.members[member] = (archive, name)
            self.groups = {}
            for member in sorted(self.members):
                try:
                    header = self.read(member, header_only=True)
                except InvalidDicomError:
                    self.skipped += 1
                    continue
                uid = str(getattr(header, "SeriesInstanceUID", ""))
                if not uid:
                    self.skipped += 1
                    continue
                self.groups.setdefault(uid, []).append(Frame(member, header))
            if not self.groups:
                raise PipelineError("E_NO_DICOM_SERIES")
            return self
        except BaseException:
            self.resources.close()
            raise

    def __exit__(self, *args):
        self.resources.close()

    def read(self, member, header_only=False):
        boundaries(source=self.source)
        archive, name = self.members[member]
        stream = archive.open(name) if archive is not None else local_file(self.file_root, name)
        with stream as opened, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return pydicom.dcmread(
                opened, stop_before_pixels=header_only,
                specific_tags=TAGS if header_only else None,
            )

    def inventory(self):
        result = []
        for frames in self.groups.values():
            try:
                stack = validate_stack(frames)
                reason = None
            except PipelineError as exc:
                stack, reason = None, str(exc)
            result.append({
                "series_number": series_number(frames[0].header),
                "slice_count": len(frames), "supported": stack is not None,
                "reason": reason,
            })
        return {"series": result, "skipped_files": self.skipped}

    def select(self, number=None):
        candidates = []
        groups = list(self.groups.values())
        if number is not None:
            groups = [frames for frames in groups if series_number(frames[0].header) == number]
            if len(groups) != 1:
                raise PipelineError("E_SERIES_SELECTION_AMBIGUOUS_OR_MISSING")
            return validate_stack(groups[0])
        if len(groups) == 1:
            return validate_stack(groups[0])
        for frames in groups:
            try:
                candidates.append(validate_stack(frames))
            except PipelineError:
                continue
        if not candidates:
            raise PipelineError("E_NO_SUPPORTED_CT_STACK")
        return max(candidates, key=lambda stack: len(stack.frames))


def series_number(header):
    try:
        return int(header.SeriesNumber)
    except (AttributeError, TypeError, ValueError):
        return None


def numbers(header, name, length):
    try:
        value = np.asarray(getattr(header, name), dtype=np.float64)
        if value.shape != (length,) or not np.isfinite(value).all():
            raise ValueError
        return value
    except (AttributeError, TypeError, ValueError):
        raise PipelineError("E_SPATIAL_METADATA") from None


def validate_stack(frames):
    if len(frames) < 2:
        raise PipelineError("E_STACK_TOO_SHORT")
    first = frames[0].header
    try:
        orientation = numbers(first, "ImageOrientationPatient", 6)
        row, col = orientation[:3], orientation[3:]
        normal = np.cross(row, col)
        if not np.allclose([np.linalg.norm(row), np.linalg.norm(col), np.dot(row, col)], [1, 1, 0], atol=1e-5):
            raise PipelineError("E_ORIENTATION")
        if abs(normal[2]) < 0.8:
            raise PipelineError("E_NOT_AXIAL")
        pixel_spacing = numbers(first, "PixelSpacing", 2)
        if (pixel_spacing <= 0).any():
            raise PipelineError("E_SPACING")
        rows, cols = int(first.Rows), int(first.Columns)
        if min(rows, cols) < 2 or max(rows, cols) > 8192:
            raise PipelineError("E_GRID_SIZE")
        positions = []
        seen_instances = set()
        for frame in frames:
            ds = frame.header
            instance = str(getattr(ds, "SOPInstanceUID", ""))
            if instance and instance in seen_instances:
                raise PipelineError("E_DUPLICATE_SOP_INSTANCE")
            seen_instances.add(instance)
            if ds.Modality != "CT" or str(ds.SOPClassUID) != str(CTImageStorage):
                raise PipelineError("E_NOT_SINGLE_FRAME_CT")
            if int(getattr(ds, "NumberOfFrames", 1)) != 1:
                raise PipelineError("E_MULTIFRAME")
            image_type = getattr(ds, "ImageType", [])
            image_type = image_type.upper() if isinstance(image_type, str) else "\\".join(str(x).upper() for x in image_type)
            if any(word in image_type for word in ("LOCALIZER", "SCOUT", "PROJECTION")):
                raise PipelineError("E_SCOUT")
            for key in ("StudyInstanceUID", "SeriesInstanceUID", "FrameOfReferenceUID"):
                if not getattr(ds, key, None) or getattr(ds, key) != getattr(first, key, None):
                    raise PipelineError("E_SERIES_INCONSISTENT")
            if series_number(ds) != series_number(first) or (int(ds.Rows), int(ds.Columns)) != (rows, cols):
                raise PipelineError("E_GRID_INCONSISTENT")
            if not np.allclose(numbers(ds, "ImageOrientationPatient", 6), orientation, rtol=0, atol=1e-5):
                raise PipelineError("E_ORIENTATION_INCONSISTENT")
            if not np.allclose(numbers(ds, "PixelSpacing", 2), pixel_spacing, rtol=0, atol=1e-5):
                raise PipelineError("E_SPACING_INCONSISTENT")
            if (int(ds.SamplesPerPixel) != 1 or ds.PhotometricInterpretation != "MONOCHROME2"
                    or "ModalityLUTSequence" in ds or "RealWorldValueMappingSequence" in ds
                    or getattr(ds, "RescaleType", "HU") != "HU"):
                raise PipelineError("E_INTENSITY_UNSUPPORTED")
            if (int(ds.BitsAllocated) not in (8, 16) or not 1 <= int(ds.BitsStored) <= int(ds.BitsAllocated)
                    or int(ds.HighBit) != int(ds.BitsStored) - 1 or int(ds.PixelRepresentation) not in (0, 1)):
                raise PipelineError("E_PIXEL_ENCODING")
            slope, intercept = float(ds.RescaleSlope), float(ds.RescaleIntercept)
            if not np.isfinite([slope, intercept]).all() or slope == 0:
                raise PipelineError("E_HU_TRANSFORM")
            positions.append(numbers(ds, "ImagePositionPatient", 3))
        positions = np.asarray(positions)
        order = np.argsort(positions @ normal, kind="stable")
        positions = positions[order]
        projected_steps = np.diff(positions @ normal)
        if (projected_steps <= 1e-4).any():
            raise PipelineError("E_DUPLICATE_POSITION")
        displacement = (positions[-1] - positions[0]) / (len(frames) - 1)
        if not np.allclose(np.diff(positions, axis=0), displacement, rtol=1e-3, atol=0.01):
            raise PipelineError("E_NONUNIFORM_STACK")
        expected = positions[0] + np.arange(len(frames))[:, None] * displacement
        if not np.allclose(positions, expected, rtol=0, atol=0.02):
            raise PipelineError("E_NONUNIFORM_STACK")
        affine = np.eye(4)
        affine[:3, 0] = row * pixel_spacing[1]
        affine[:3, 1] = col * pixel_spacing[0]
        affine[:3, 2] = displacement
        affine[:3, 3] = positions[0]
        return Stack([frames[index] for index in order], affine, (len(frames), rows, cols))
    except (AttributeError, ValueError, TypeError, OverflowError):
        raise PipelineError("E_DICOM_METADATA") from None


def decode_hu(collection, frame):
    ds = collection.read(frame.member)
    # Revalidate critical headers in case the caller replaced a source after inventory.
    for tag in TAGS:
        if ds.get(tag) != frame.header.get(tag):
            raise PipelineError("E_SOURCE_CHANGED")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pixels = ds.pixel_array
        if pixels.shape != (int(ds.Rows), int(ds.Columns)):
            raise PipelineError("E_PIXEL_SHAPE")
        hu = pixels.astype(np.float32)
        hu *= float(ds.RescaleSlope)
        hu += float(ds.RescaleIntercept)
        if not np.isfinite(hu).all():
            raise PipelineError("E_HU_NONFINITE")
        return hu
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("E_PIXEL_DECODE") from None
