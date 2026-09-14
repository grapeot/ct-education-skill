"""Runtime-only synthetic fixtures, always outside the checkout."""

from contextlib import redirect_stderr, redirect_stdout
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
from scipy import ndimage as ndi
from PIL import Image
from pydicom import dcmread
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.pixels import get_decoder
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, JPEGLosslessSV1, generate_uid

from ct_education.cli import main
from ct_education.dicom import Collection, decode_hu, validate_stack
from ct_education.pipeline import annotations_from_file, build, ras_bounds
from ct_education.safety import REPO, PipelineError, boundaries, disjoint, local_file
from ct_education.segmentation import LAYER_INFO, airway_candidates, mesh_for_mask, physical_disk, segment
from ct_education.server import create_server, render_slice


def synthetic_volume(shape=(24, 64, 64)):
    z, y, x = np.indices(shape)
    volume = np.full(shape, -1000, dtype=np.int16)
    body = ((x - 32) / 26) ** 2 + ((y - 31) / 26) ** 2 < 1
    volume[body] = 30
    lungs = (((x - 21) / 8) ** 2 + ((y - 30) / 15) ** 2 < 1) | (((x - 43) / 8) ** 2 + ((y - 30) / 15) ** 2 < 1)
    volume[lungs & body] = -800
    volume[(((x - 32) ** 2 + (y - 25) ** 2) <= 4) & (z > 12)] = -950
    volume[(((x - 21) ** 2 + (y - 30) ** 2) <= 4)] = 80
    volume[(((x - 43) ** 2 + (y - 30) ** 2) <= 4)] = 80
    volume[((x - 32) ** 2 + (y - 50) ** 2) < 9] = 500
    volume[y >= 61] = 500
    return volume


def write_series(root, volume=None, number=7, orientation=None, displacement=None, origin=None):
    root.mkdir(exist_ok=True)
    if volume is None:
        volume = synthetic_volume()
    orientation = np.array(orientation if orientation is not None else [1, 0, 0, 0, 1, 0], dtype=float)
    displacement = np.array(displacement if displacement is not None else [0, 0, 2], dtype=float)
    origin = np.array(origin if origin is not None else [10, 20, 30], dtype=float)
    study, series, reference = generate_uid(), generate_uid(), generate_uid()
    for k in range(len(volume)):
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = CTImageStorage
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
        ds.StudyInstanceUID, ds.SeriesInstanceUID, ds.FrameOfReferenceUID = study, series, reference
        ds.SeriesNumber = number
        ds.Modality = "CT"
        ds.PatientName = "SYNTHETIC^DO_NOT_SERVE"
        ds.PatientID = "SYNTHETIC_IDENTIFIER"
        ds.ImageType = ["ORIGINAL", "PRIMARY", "AXIAL"]
        ds.InstanceNumber = 999 - k
        ds.Rows, ds.Columns = volume.shape[1:]
        ds.ImageOrientationPatient = orientation.tolist()
        ds.ImagePositionPatient = (origin + displacement * k).tolist()
        ds.PixelSpacing = [2, 2]
        ds.SliceThickness = 9
        ds.SamplesPerPixel = 1
        ds.PhotometricInterpretation = "MONOCHROME2"
        ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
        ds.PixelRepresentation = 1
        ds.RescaleSlope, ds.RescaleIntercept, ds.RescaleType = 2, -1000, "HU"
        ds.PixelData = ((volume[k].astype(np.int32) + 1000) // 2).astype("<i2").tobytes()
        ds.save_as(root / f"frame-{len(volume) - k:04d}.dcm", enforce_file_format=True)
    return volume


def branching_airway_phantom(leak=False):
    k, j, i = np.indices((64, 96, 96))
    body = ((i - 48) / 44) ** 2 + ((j - 48) / 43) ** 2 < 1
    lungs = ((((i - 20) / 12) ** 2 + ((j - 65) / 19) ** 2 < 1)
             | (((i - 76) / 12) ** 2 + ((j - 65) / 19) ** 2 < 1)) & body
    trunk = ((i - 48) ** 2 + (j - 35) ** 2 <= 16) & (k >= 40)
    offset = np.maximum(0, 40 - k) * 0.75
    branches = (((i - (48 - offset)) ** 2 + (j - 35) ** 2 <= 6.25)
                 | ((i - (48 + offset)) ** 2 + (j - 35) ** 2 <= 6.25)) & (k >= 12) & (k < 40)
    airway = trunk | branches
    volume = np.full(k.shape, -1000, dtype=np.float32)
    volume[body] = 30
    volume[lungs | airway] = -950
    if leak:
        for plane in range(12, 24):
            for x, target in ((int(round(48 - (40 - plane) * 0.75)), 20), (int(round(48 + (40 - plane) * 0.75)), 76)):
                volume[plane, 35:66, x] = -950
                volume[plane, 65, min(x, target):max(x, target) + 1] = -950
    return volume, body, airway, lungs, np.diag([1.5, 1.5, 2.0, 1])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()).resolve()
        if base == REPO or REPO in base.parents:
            self.fail("external-temp-required")
        self.temp = tempfile.TemporaryDirectory(prefix="ct-edu-test-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        disjoint(REPO, self.root)
        self.source = self.root / "source"
        self.workspace = self.root / "result"

    def test_realpath_disjoint_and_symlink_ancestors(self):
        self.source.mkdir()
        for first, second in ((self.source, self.source), (self.root, self.source), (self.source, self.root)):
            with self.subTest(case="overlap"), self.assertRaises(PipelineError):
                disjoint(first, second)
        alias = self.root / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(PipelineError):
            disjoint(self.source, alias / "missing" / "leaf")
        repo_alias = self.root / "repo-alias"
        repo_alias.symlink_to(REPO, target_is_directory=True)
        with self.assertRaises(PipelineError):
            boundaries(source=repo_alias / "missing")
        boundaries(source=self.source, workspace=self.workspace)
        with self.assertRaises(PipelineError):
            boundaries(source=self.source, workspace=self.source / "result")

    def test_no_follow_file_and_directory(self):
        self.source.mkdir()
        (self.root / "probe").write_text("synthetic")
        (self.source / "link").symlink_to(self.root / "probe")
        with self.assertRaises(OSError), local_file(self.source, "link"):
            pass
        (self.source / "nested").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError), local_file(self.source, "nested/probe"):
            pass
        with self.assertRaises(PipelineError), local_file(self.source, "../probe"):
            pass

    def test_physical_sort_affine_hu_and_roundtrip(self):
        angle = 0.15
        orientation = [1, 0, 0, 0, np.cos(angle), np.sin(angle)]
        normal = np.cross(orientation[:3], orientation[3:])
        displacement = normal * 2 + np.array([0.15, 0, 0])
        expected = write_series(self.source, orientation=orientation, displacement=displacement)
        with Collection(self.source) as collection:
            stack = collection.select()
            self.assertEqual(stack.shape, expected.shape)
            np.testing.assert_allclose(stack.affine[:3, 2], displacement)
            np.testing.assert_allclose(decode_hu(collection, stack.frames[5]), expected[5])
            positions = [float(np.dot(frame.header.ImagePositionPatient, normal)) for frame in stack.frames]
            self.assertEqual(positions, sorted(positions))
            point = np.array([12.4, 20.7, 8.2, 1])
            lps = stack.affine @ point
            np.testing.assert_allclose(np.linalg.inv(stack.affine) @ lps, point)
            np.testing.assert_allclose(stack.affine @ [0, 0, 9, 1], [*stack.frames[9].header.ImagePositionPatient, 1])

    def test_per_slice_rescale_and_signed_pixels(self):
        write_series(self.source, volume=np.full((3, 8, 8), -1200, dtype=np.int16))
        last_file = self.source / "frame-0001.dcm"
        ds = dcmread(last_file)
        ds.RescaleSlope, ds.RescaleIntercept = 1, 0
        ds.save_as(last_file, enforce_file_format=True)
        with Collection(self.source) as collection:
            stack = collection.select()
            self.assertEqual(float(decode_hu(collection, stack.frames[0])[0, 0]), -1200)
            self.assertEqual(float(decode_hu(collection, stack.frames[2])[0, 0]), -100)
        ds.PixelRepresentation = 0
        ds.PixelData = np.full((8, 8), 40000, dtype="<u2").tobytes()
        ds.save_as(last_file, enforce_file_format=True)
        with Collection(self.source) as collection:
            self.assertEqual(float(decode_hu(collection, collection.select().frames[2])[0, 0]), 40000)

    def test_reject_invalid_stacks(self):
        write_series(self.source)
        mutations = [
            ("Modality", "MR"), ("NumberOfFrames", 2), ("ImageType", ["LOCALIZER"]),
            ("PixelSpacing", [2, 3]), ("ImageOrientationPatient", [0, 1, 0, 1, 0, 0]),
            ("ImagePositionPatient", [10, 20, 30]), ("ImagePositionPatient", [10, 20, 99]),
            ("RescaleSlope", 0), ("PhotometricInterpretation", "MONOCHROME1"),
        ]
        for key, value in mutations:
            with self.subTest(field=key), Collection(self.source) as collection:
                stack = collection.select()
                setattr(stack.frames[1].header, key, value)
                with self.assertRaises(PipelineError):
                    validate_stack(stack.frames)
        with Collection(self.source) as collection:
            stack = collection.select()
            del stack.frames[1].header.ImagePositionPatient
            with self.assertRaises(PipelineError):
                validate_stack(stack.frames)

    def test_select_largest_valid_series_and_explicit_selection(self):
        write_series(self.source)
        write_series(self.source / "other", volume=np.zeros((4, 8, 8), dtype=np.int16), number=8)
        with Collection(self.source) as collection:
            self.assertEqual(collection.select().shape[0], 24)
            self.assertEqual(collection.select(8).shape[0], 4)
            with self.assertRaises(PipelineError):
                collection.select(999)
        write_series(self.source / "ambiguous", volume=np.zeros((3, 8, 8), dtype=np.int16), number=8)
        with Collection(self.source) as collection, self.assertRaises(PipelineError):
            collection.select(8)

    def test_zip_inventory_decode_and_traversal_rejected(self):
        expected = write_series(self.source)
        archive = self.root / "collection.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
            for path in self.source.iterdir():
                stream.write(path, "nested/" + path.name)
        with Collection(archive) as collection:
            stack = collection.select(7)
            np.testing.assert_array_equal(decode_hu(collection, stack.frames[0]), expected[0])
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as stream:
            stream.writestr("../escape", "synthetic")
        with self.assertRaises(PipelineError), Collection(bad):
            pass

    def test_jpeg_lossless_decoder_available(self):
        self.assertIn("pylibjpeg", get_decoder(JPEGLosslessSV1).available_plugins)

    def test_directory_merges_split_zip_series_and_builds(self):
        expected = np.broadcast_to(np.arange(6, dtype=np.int16)[:, None, None] * 20 - 900, (6, 8, 8)).copy()
        write_series(self.source, volume=expected)
        files = sorted(self.source.iterdir())
        packages = self.root / "packages"
        (packages / "nested").mkdir(parents=True)
        for part, name in enumerate(("a.zip", "nested/b.ZIP")):
            with zipfile.ZipFile(packages / name, "w", zipfile.ZIP_DEFLATED) as archive:
                for index, path in enumerate(files[part::2]):
                    # Identical member names in different packages must remain independent.
                    archive.write(path, f"images/frame-{index}.dcm")
        with Collection(packages) as collection:
            inventory = collection.inventory()
            self.assertEqual(inventory["series"], [{"series_number": 7, "slice_count": 6, "supported": True, "reason": None}])
            self.assertEqual(inventory["skipped_files"], 0)
            stack = collection.select(7)
            self.assertEqual(len({frame.member for frame in stack.frames}), 6)
            np.testing.assert_allclose(stack.affine[:3, 2], [0, 0, 2])
            for k, frame in enumerate(stack.frames):
                np.testing.assert_array_equal(decode_hu(collection, frame), expected[k])
            archives = {archive for archive, _ in collection.members.values()}
            streams = [archive.fp for archive in archives]
            self.assertEqual(len(archives), 2)
        self.assertTrue(all(archive.fp is None for archive in archives))
        self.assertTrue(all(stream.closed for stream in streams))
        self.assertEqual(list(packages.rglob("*.dcm")), [])
        manifest = build(packages, self.workspace)
        self.assertEqual(manifest["source"]["slice_count"], 6)
        np.testing.assert_array_equal(np.load(self.workspace / "volume.npy"), expected)

    def test_directory_merges_loose_dicom_and_zip_frames(self):
        expected = write_series(self.source, volume=np.full((6, 8, 8), -800, dtype=np.int16))
        files = sorted(self.source.iterdir())
        packages = self.root / "packages"
        packages.mkdir()
        with zipfile.ZipFile(packages / "a.zip", "w") as archive:
            for path in files[:4]:
                archive.write(path, path.name)
        for path in files[4:]:
            (packages / path.name).write_bytes(path.read_bytes())
        (packages / "note.txt").write_text("synthetic non-DICOM file")
        with Collection(packages) as collection:
            self.assertEqual(collection.inventory()["skipped_files"], 1)
            stack = collection.select()
            self.assertEqual(stack.shape, expected.shape)
            for k, frame in enumerate(stack.frames):
                np.testing.assert_array_equal(decode_hu(collection, frame), expected[k])

    def test_bad_second_zip_paths_close_all_resources(self):
        write_series(self.source, volume=np.zeros((2, 8, 8), dtype=np.int16))
        packages = self.root / "packages"
        packages.mkdir()
        with zipfile.ZipFile(packages / "a.zip", "w") as archive:
            archive.write(self.source / "frame-0001.dcm", "slice.dcm")
        original_zip = zipfile.ZipFile
        for name in ("../escape.dcm", "/escape.dcm", "nested\\escape.dcm", "../escape/"):
            with self.subTest(member=name):
                with original_zip(packages / "b.zip", "w") as archive:
                    archive.writestr(name, "synthetic")
                opened = []

                def tracked_zip(*args, **kwargs):
                    archive = original_zip(*args, **kwargs)
                    opened.append((archive, archive.fp))
                    return archive

                with patch("ct_education.dicom.zipfile.ZipFile", side_effect=tracked_zip):
                    with self.assertRaisesRegex(PipelineError, "^E_ZIP_MEMBER_PATH$"), Collection(packages):
                        pass
                self.assertEqual(len(opened), 2)
                self.assertTrue(all(archive.fp is None and stream.closed for archive, stream in opened))

    def test_second_zip_size_symlink_and_duplicate_rules(self):
        write_series(self.source, volume=np.zeros((2, 8, 8), dtype=np.int16))
        packages = self.root / "packages"
        packages.mkdir()
        with zipfile.ZipFile(packages / "a.zip", "w") as archive:
            archive.write(self.source / "frame-0001.dcm", "slice.dcm")
        original_zip = zipfile.ZipFile
        for rule, code in (("size", "E_ZIP_MEMBER_SIZE"), ("symlink", "E_INPUT_SYMLINK"), ("duplicate", "E_ZIP_DUPLICATE_MEMBER")):
            with self.subTest(rule=rule):
                item = zipfile.ZipInfo("slice.dcm")
                if rule == "symlink":
                    item.create_system = 3
                    item.external_attr = 0o120777 << 16
                with original_zip(packages / "b.zip", "w") as archive:
                    archive.writestr(item, "synthetic")
                    if rule == "duplicate":
                        with self.assertWarns(UserWarning):
                            archive.writestr("slice.dcm", "synthetic")
                opened = []

                def tracked_zip(*args, **kwargs):
                    archive = original_zip(*args, **kwargs)
                    opened.append((archive, archive.fp))
                    if rule == "size" and len(opened) == 2:
                        archive.filelist[0].file_size = 512 * 1024 * 1024 + 1
                    return archive

                with patch("ct_education.dicom.zipfile.ZipFile", side_effect=tracked_zip):
                    with self.assertRaisesRegex(PipelineError, "^" + code + "$"), Collection(packages):
                        pass
                self.assertEqual(len(opened), 2)
                self.assertTrue(all(archive.fp is None and stream.closed for archive, stream in opened))

    def test_repeated_sop_across_packages_rejected_not_deduplicated(self):
        write_series(self.source, volume=np.zeros((2, 8, 8), dtype=np.int16))
        packages = self.root / "packages"
        packages.mkdir()
        for name in ("a.zip", "b.zip"):
            with zipfile.ZipFile(packages / name, "w") as archive:
                archive.write(self.source / "frame-0001.dcm", "slice.dcm")
        with Collection(packages) as collection:
            inventory = collection.inventory()["series"][0]
            self.assertEqual(inventory["slice_count"], 2)
            self.assertFalse(inventory["supported"])
            self.assertEqual(inventory["reason"], "E_DUPLICATE_SOP_INSTANCE")
            for number in (None, 7):
                with self.assertRaisesRegex(PipelineError, "^E_DUPLICATE_SOP_INSTANCE$"):
                    collection.select(number)

    def test_directory_rejects_archive_symlinks(self):
        packages = self.root / "packages"
        packages.mkdir()
        with zipfile.ZipFile(self.root / "outside.zip", "w") as archive:
            archive.writestr("note.txt", "synthetic")
        (packages / "linked.zip").symlink_to(self.root / "outside.zip")
        with self.assertRaisesRegex(PipelineError, "^E_INPUT_SYMLINK$"), Collection(packages):
            pass

    def test_candidate_shapes_table_airway_and_mesh_bounds(self):
        volume = synthetic_volume()
        affine = np.diag([2, 2, 2, 1]).astype(float)
        masks, label_affine, stride, messages = segment(volume, affine)
        for name, mask in masks.items():
            self.assertEqual(mask.shape, volume[::stride[0], ::stride[1], ::stride[2]].shape)
            self.assertTrue(mask.any(), name)
            self.assertFalse(mask[:, -3:, :].any(), name)
        self.assertFalse((masks["lungs"] & masks["airways"]).any())
        self.assertTrue((masks["vessels"] <= masks["lungs"]).all())
        np.testing.assert_allclose(label_affine, affine @ np.diag([*stride[::-1], 1]))
        self.assertTrue(messages)
        mesh = mesh_for_mask(masks["lungs"], label_affine, volume.shape, stride)
        positions = np.array(mesh["positions"]).reshape(-1, 3)
        faces = np.array(mesh["indices"]).reshape(-1, 3)
        bounds = ras_bounds(volume.shape, np.diag([-1, -1, 1, 1]) @ affine)
        self.assertTrue((positions >= np.array(bounds["min"]) - 1e-3).all())
        self.assertTrue((positions <= np.array(bounds["max"]) + 1e-3).all())
        self.assertLess(int(faces.max()), len(positions))

    def test_surface_affine_oblique_spatial_bounds(self):
        mask = np.zeros((8, 9, 10), dtype=bool)
        mask[2:6, 2:7, 2:8] = True
        affine = np.array([[2, 0, 0.2, 10], [0, 1.9, -0.4, 20], [0, 0.2, 2, 30], [0, 0, 0, 1]])
        mesh = mesh_for_mask(mask, affine)
        ras = np.array(mesh["positions"]).reshape(-1, 3)
        points = (np.c_[ras, np.ones(len(ras))] @ np.linalg.inv(np.diag([-1, -1, 1, 1]) @ affine).T)[:, :3]
        np.testing.assert_allclose(points.min(axis=0), [1.5, 1.5, 1.5], atol=1e-3)
        np.testing.assert_allclose(points.max(axis=0), [7.5, 6.5, 5.5], atol=1e-3)

    def test_reduced_grid_transform_and_empty_candidates(self):
        volume = np.full((205, 16, 16), -1000, dtype=np.float32)
        affine = np.diag([0.5, 0.5, 0.5, 1])
        masks, label_affine, stride, messages = segment(volume, affine)
        self.assertTrue((stride > 1).any())
        np.testing.assert_allclose(label_affine, affine @ np.diag([*stride[::-1], 1]))
        for mask in masks.values():
            self.assertEqual(mask.shape, volume[::stride[0], ::stride[1], ::stride[2]].shape)
            self.assertFalse(mask.any())
        self.assertTrue(any("omitted" in message for message in messages))

    def test_y_airway_recovers_both_branches_without_native_changes(self):
        volume, body, expected, lungs, affine = branching_airway_phantom()
        original = volume.copy()
        volume.flags.writeable = False
        masks, label_affine, stride, messages = segment(volume, affine)
        airway = masks["airways"]
        self.assertEqual(list(LAYER_INFO), ["lungs", "airways", "vessels", "bones"])
        np.testing.assert_array_equal(stride, [1, 1, 1])
        np.testing.assert_array_equal(label_affine, affine)
        np.testing.assert_array_equal(volume, original)
        np.testing.assert_array_equal(airway, expected)
        self.assertEqual(ndi.label(airway, np.ones((3, 3, 3)))[1], 1)
        self.assertEqual(ndi.label(airway[16], np.ones((3, 3)))[1], 2)
        self.assertFalse((airway & lungs).any())
        self.assertFalse((airway & ~body).any())
        self.assertFalse((airway & masks["lungs"]).any())
        self.assertFalse(any("no sustained bifurcation" in message for message in messages))
        repeated, _, _, _ = segment(volume, affine)
        np.testing.assert_array_equal(repeated["airways"], airway)

    def test_y_airway_stops_before_connected_giant_lung_pockets(self):
        volume, body, expected, lungs, affine = branching_airway_phantom(leak=True)
        airway, messages = airway_candidates(volume, body, affine)
        self.assertFalse((airway & lungs).any())
        self.assertFalse((airway & ~expected).any())
        self.assertFalse(airway[:24].any())
        np.testing.assert_array_equal(airway[24:], expected[24:])
        self.assertEqual(ndi.label(airway, np.ones((3, 3, 3)))[1], 1)
        self.assertTrue(any("inseparable air pockets" in message for message in messages))

    def test_diagonal_airway_connections_survive_final_component_filter(self):
        volume = np.full((24, 48, 48), 30, dtype=np.float32)
        body = np.zeros_like(volume, dtype=bool)
        body[:, 4:44, 4:44] = True
        expected = np.zeros_like(body)
        expected[18:, 19:21, 23:25] = True
        for k in range(9, 18):
            expected[k, 20 - (17 - k), 24 - (17 - k)] = True
        volume[expected] = -950
        airway, messages = airway_candidates(volume, body, np.diag([2, 2, 2, 1]))
        np.testing.assert_array_equal(airway, expected)
        self.assertGreater(ndi.label(airway)[1], 1)
        self.assertEqual(ndi.label(airway, np.ones((3, 3, 3)))[1], 1)
        self.assertTrue(any("no sustained bifurcation" in message for message in messages))

    def test_airway_volume_limit_discards_broad_growth(self):
        k, j, i = np.indices((100, 64, 64))
        radius = np.where(k >= 98, 3, 6)
        air = (j - 32) ** 2 + (i - 32) ** 2 <= radius ** 2
        volume = np.full(k.shape, 30, dtype=np.float32)
        volume[air] = -950
        body = np.ones_like(air)
        affine = np.diag([2, 2, 5, 1])
        self.assertGreater(air.sum() * abs(np.linalg.det(affine[:3, :3])), 80_000)
        airway, messages = airway_candidates(volume, body, affine)
        self.assertFalse(airway[:98].any())
        np.testing.assert_array_equal(airway[98:], air[98:])
        self.assertTrue(any("growth exceeded" in message for message in messages))

    def test_airway_superior_seed_follows_affine_not_array_direction(self):
        volume, body, expected, _, affine = branching_airway_phantom()
        reversed_affine = affine.copy()
        reversed_affine[:3, 3] += affine[:3, 2] * (len(volume) - 1)
        reversed_affine[:3, 2] *= -1
        airway, _ = airway_candidates(volume[::-1], body[::-1], reversed_affine)
        np.testing.assert_array_equal(airway, expected[::-1])

    def test_fragmented_lung_air_cannot_supply_airway_seed(self):
        k, j, i = np.indices((24, 64, 64))
        body = np.ones(k.shape, dtype=bool)
        volume = np.full(k.shape, 30, dtype=np.float32)
        volume[(j - 32) ** 2 + (i - 32) ** 2 < 15 ** 2] = -750
        volume[(j - 32) ** 2 + (i - 32) ** 2 < 3 ** 2] = -950
        airway, messages = airway_candidates(volume, body, np.diag([2, 2, 2, 1]))
        self.assertFalse(airway.any())
        self.assertTrue(any("no supported superior seed" in message for message in messages))

    def test_physical_morphology_footprint_respects_anisotropic_spacing(self):
        footprint = physical_disk([1, 2], 1.5)
        j, i = np.argwhere(footprint).T - (np.asarray(footprint.shape) // 2)[:, None]
        self.assertTrue(((j ** 2 + (2 * i) ** 2) <= 1.5 ** 2).all())
        self.assertEqual(int(footprint.sum()), 3)
        self.assertEqual(int(physical_disk([2, 2], 1.5).sum()), 1)

    def test_display_smoothing_is_bounded_deterministic_and_labels_unchanged(self):
        k, j, i = np.indices((18, 18, 18))
        mask = (i - 8) ** 2 + (j - 8) ** 2 + (k - 8) ** 2 <= 36
        original = mask.copy()
        affine = np.array([[1, 0, 0.2, 10], [0, 1.5, 0, 20], [0, 0, 2, 30], [0, 0, 0, 1]])
        raw = mesh_for_mask(mask, affine, smooth=False)
        smooth = mesh_for_mask(mask, affine)
        np.testing.assert_array_equal(mask, original)
        self.assertEqual(raw["indices"], smooth["indices"])
        self.assertEqual(smooth, mesh_for_mask(mask, affine))
        vertices = np.array(smooth["positions"]).reshape(-1, 3)
        raw_vertices = np.array(raw["positions"]).reshape(-1, 3)
        motion = np.linalg.norm(vertices - raw_vertices, axis=1)
        self.assertGreater(motion.max(), 0)
        limit = min(0.75, 0.35 * np.linalg.svd(affine[:3, :3], compute_uv=False).min())
        self.assertLessEqual(motion.max(), limit + 0.0002)
        bounds = ras_bounds(mask.shape, np.diag([-1, -1, 1, 1]) @ affine)
        self.assertTrue((vertices >= np.asarray(bounds["min"]) - 0.0002).all())
        self.assertTrue((vertices <= np.asarray(bounds["max"]) + 0.0002).all())
        faces = np.array(smooth["indices"]).reshape(-1, 3)
        raw_area = np.linalg.norm(np.cross(raw_vertices[faces[:, 1]] - raw_vertices[faces[:, 0]], raw_vertices[faces[:, 2]] - raw_vertices[faces[:, 0]]), axis=1).sum()
        smooth_area = np.linalg.norm(np.cross(vertices[faces[:, 1]] - vertices[faces[:, 0]], vertices[faces[:, 2]] - vertices[faces[:, 0]]), axis=1).sum()
        self.assertLess(smooth_area, raw_area)

    def test_annotations_validate_and_sanitize(self):
        annotation_file = self.root / "annotations.json"
        item = {"id": "synthetic", "label": "SYNTHETIC_PRIVATE_TEXT", "position_ras": [2, 2, 2], "radius_mm": 2}
        annotation_file.write_text(json.dumps([item]))
        result = annotations_from_file(annotation_file, (8, 8, 8), np.eye(4))
        self.assertNotIn("SYNTHETIC_PRIVATE_TEXT", json.dumps(result))
        self.assertEqual(result[0]["review_status"], "unverified candidate")
        for key, value in (("radius_mm", float("nan")), ("radius_mm", float("inf")), ("radius_mm", -1), ("position_ras", [float("nan"), 0, 0]), ("position_ras", [100, 0, 0])):
            with self.subTest(field=key):
                annotation_file.write_text(json.dumps([{**item, key: value}]))
                with self.assertRaises(PipelineError):
                    annotations_from_file(annotation_file, (8, 8, 8), np.eye(4))

    def test_build_native_cache_manifest_and_no_overwrite(self):
        volume = write_series(self.source)
        manifest = build(self.source, self.workspace, 7)
        cached = np.load(self.workspace / "volume.npy", allow_pickle=False)
        np.testing.assert_array_equal(cached, volume)
        self.assertTrue((self.workspace / "labels.npy").is_file())
        self.assertTrue((self.workspace / "labels-grid.json").is_file())
        self.assertEqual(set(manifest), {"schema_version", "shape", "spacing", "affine_lps", "affine_ras", "bounds_ras", "layers", "annotations", "warnings", "source", "tour"})
        serialized = json.dumps(manifest)
        self.assertNotIn("SYNTHETIC", serialized)
        self.assertNotIn("UID", serialized)
        self.assertNotIn(str(self.source), serialized)
        with self.assertRaisesRegex(PipelineError, "E_WORKSPACE_EXISTS"):
            build(self.source, self.workspace)
        np.testing.assert_array_equal(np.load(self.workspace / "volume.npy"), volume)

    def test_failure_does_not_publish_manifest(self):
        write_series(self.source)
        with patch("ct_education.pipeline.segment", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                build(self.source, self.workspace)
        self.assertFalse(self.workspace.exists())
        self.assertEqual(list(self.root.glob(".ct-edu-stage-*")), [])

    def test_mid_publication_failure_has_no_complete_manifest(self):
        write_series(self.source)
        rename = os.rename

        def fail_second(src, dst, **kwargs):
            if src == "labels.npy":
                raise OSError("synthetic failure")
            return rename(src, dst, **kwargs)

        with patch("ct_education.pipeline.os.rename", side_effect=fail_second), self.assertRaises(OSError):
            build(self.source, self.workspace)
        self.assertFalse((self.workspace / "manifest.json").exists())
        with self.assertRaises((OSError, PipelineError)):
            create_server(self.workspace, port=0)

    def test_cli_inspect_no_output_required_and_errors_sanitized(self):
        write_series(self.source)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(["inspect", "--input", str(self.source)]), 0)
        self.assertEqual(json.loads(stdout.getvalue())["series"][0]["slice_count"], 24)
        self.assertNotIn("SYNTHETIC", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        with redirect_stderr(stderr):
            self.assertEqual(main(["inspect", "--input", str(self.root / "missing")]), 2)
            self.assertEqual(main(["build", "--private-synthetic-value"]), 2)
        self.assertNotIn(str(self.root), stderr.getvalue())
        self.assertNotIn("private-synthetic", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_native_slices_no_flips(self):
        volume = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
        for axis, expected in (("axial", volume[1]), ("coronal", volume[:, 1]), ("sagittal", volume[:, :, 1])):
            png = render_slice(volume, axis, 1, 127.5, 255)
            pixels = np.asarray(Image.open(io.BytesIO(png)))
            np.testing.assert_array_equal(pixels, expected.astype(np.uint8))

    def test_server_routes_origin_traversal_voxel_and_no_store(self):
        write_series(self.source)
        manifest = build(self.source, self.workspace)
        static_repo = self.root / "generic-app"
        static = static_repo / "frontend" / "dist"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<html><body>Generic synthetic viewer</body></html>")
        (static / "assets" / "index-12345678.js").write_text("export const synthetic = true;")
        (static / "assets" / "leak-12345678.js").symlink_to(self.workspace / "provenance.json")
        with patch("ct_education.server.REPO", static_repo):
            server = create_server(self.workspace, port=0, require_frontend=True)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        port = server.server_address[1]

        def request(path, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                connection.request("GET", path, headers=headers or {})
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.getheader("Cache-Control"), "no-store")
                self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
                return response.status, dict(response.getheaders()), body
            finally:
                connection.close()

        status, _, body = request("/api/manifest")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), manifest)
        self.assertEqual(request("/")[0], 200)
        self.assertEqual(request("/assets/index-12345678.js")[0], 200)
        self.assertEqual(request("/assets/leak-12345678.js")[0], 404)
        status, _, body = request("/api/voxel?i=10&j=20&k=3")
        self.assertEqual(status, 200)
        voxel = json.loads(body)
        np.testing.assert_allclose(voxel["lps"], [30, 60, 36])
        np.testing.assert_allclose(voxel["ras"], [-30, -60, 36])
        status, headers, body = request("/api/slice?axis=coronal&index=20&wc=-600&ww=1500")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Slice-Index"], "20")
        self.assertEqual(Image.open(io.BytesIO(body)).size, (64, 24))
        for layer in manifest["layers"]:
            self.assertEqual(request("/api/mesh/" + layer["id"])[0], 200)
        for path in ("/../provenance.json", "/%2e%2e/provenance.json", "/api/mesh/../../provenance", "/provenance.json", "/volume.npy", "/labels.npy", "/assets/main-12345678.js.map", "/src/ct_education/cli.py", "/api/voxel?i=-1&j=0&k=0", "/api/slice?axis=axial&index=0&ww=nan", "/api/slice?axis=axial&index=0&index=1"):
            with self.subTest(route=path):
                self.assertIn(request(path)[0], (400, 404))
        self.assertEqual(request("/api/manifest", {"Host": "external.invalid"})[0], 403)
        self.assertEqual(request("/api/manifest", {"Origin": "https://external.invalid"})[0], 403)
        self.assertEqual(request("/api/manifest", {"Origin": f"http://127.0.0.1:{port + 1}"})[0], 403)
        self.assertEqual(request("/api/manifest", {"Origin": "null"})[0], 403)
        self.assertEqual(request("/api/manifest", {"Origin": f"http://localhost:{port}"})[0], 200)
        if manifest["layers"]:
            name = manifest["layers"][0]["id"]
            mesh = self.workspace / "meshes" / f"{name}.json"
            mesh.unlink()
            mesh.symlink_to(self.workspace / "provenance.json")
            self.assertEqual(request("/api/mesh/" + name)[0], 404)


if __name__ == "__main__":
    unittest.main()
