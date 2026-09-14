"""Video safety and orchestration tests; fixtures never enter the checkout."""

from contextlib import contextmanager, ExitStack, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from ct_education.cli import main
from ct_education.safety import REPO, PipelineError, disjoint, write_json
from ct_education.video import _browser_environment, _capture, _dependencies, _same_origin, render_video, validate_options


class VideoTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()).resolve()
        if base == REPO or REPO in base.parents:
            self.fail("external-temp-required")
        self.temp = tempfile.TemporaryDirectory(prefix="ct-edu-video-test-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        disjoint(REPO, self.root)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(mode=0o700)
        self.manifest = {
            "schema_version": 1, "shape": [8, 8, 8], "spacing": [1, 1, 1],
            "affine_lps": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "affine_ras": [[-1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "bounds_ras": {"min": [-7.5, -7.5, -0.5], "max": [0.5, 0.5, 7.5]},
            "layers": [{"id": "lungs", "name": "Synthetic", "color": "#65c8cc",
                        "description": "Synthetic", "review_status": "algorithmic candidate",
                        "mesh": "meshes/lungs.json"}],
            "annotations": [], "warnings": [], "source": {"modality": "CT", "slice_count": 8},
            "tour": [{"id": "overview", "target_ras": [-3.5, -3.5, 3.5]}],
        }
        write_json(self.workspace, "manifest.json", self.manifest)

    @contextmanager
    def runtime(self, real_encoder=False):
        with ExitStack() as stack:
            dependency = stack.enter_context(patch("ct_education.video._dependencies"))
            sync = MagicMock()
            dependency.return_value = (shutil.which("ffmpeg") if real_encoder else "ffmpeg", sync)
            chromium = sync.return_value.__enter__.return_value.chromium
            context = chromium.launch_persistent_context.return_value
            page = context.new_page.return_value
            page.evaluate.side_effect = lambda script, *args: {
                "window.ctEducation.meshCount": 1,
                "window.ctEducation.tourLength": len(self.manifest["tour"]),
            }.get(script)
            image = io.BytesIO()
            Image.new("RGB", (32, 32), (40, 80, 120)).save(image, format="PNG")
            page.screenshot.return_value = image.getvalue()
            factory = stack.enter_context(patch("ct_education.video.create_server"))
            server = factory.return_value.__enter__.return_value
            server.server_address = ("127.0.0.1", 12345)
            encoder = None
            if not real_encoder:
                popen = stack.enter_context(patch("ct_education.video.subprocess.Popen"))
                encoder = popen.return_value.__enter__.return_value
                encoder.stdin = io.BytesIO()
                encoder.wait.return_value = 0
                encoder.poll.return_value = 0

                def encode(*args, **kwargs):
                    Path(args[0][-1]).write_bytes(b"synthetic-encoded-video")
                    return popen.return_value

                popen.side_effect = encode
            yield context, page, encoder, server, factory, chromium

    def test_defaults(self):
        root, relative, frames = validate_options(self.workspace)
        self.assertEqual((root, relative, frames), (self.workspace, Path("tour.mp4"), 300))

    def test_duration_bounds(self):
        for value in (0, -1, 120.1, float("nan"), float("inf"), True, "20"):
            with self.subTest(value=value), self.assertRaisesRegex(PipelineError, "^E_VIDEO_DURATION$"):
                validate_options(self.workspace, duration=value)
        self.assertEqual(validate_options(self.workspace, duration=120, fps=60)[2], 7200)
        self.assertEqual(validate_options(self.workspace, duration=0.01)[2], 1)

    def test_fps_bounds(self):
        for value in (0, -1, 61, 15.5, True):
            with self.subTest(value=value), self.assertRaisesRegex(PipelineError, "^E_VIDEO_FPS$"):
                validate_options(self.workspace, fps=value)

    def test_dimension_bounds_and_even_pixels(self):
        for width, height in ((0, 720), (1281, 720), (1280, 721), (1922, 1080), (1920, 1082), (2.0, 2)):
            with self.subTest(size=(width, height)), self.assertRaisesRegex(PipelineError, "^E_VIDEO_DIMENSIONS$"):
                validate_options(self.workspace, width=width, height=height)
        validate_options(self.workspace, width=1920, height=1080)

    def test_port_bounds(self):
        for value in (-1, 65536, True, 1.0):
            with self.subTest(value=value), self.assertRaisesRegex(PipelineError, "^E_PORT$"):
                validate_options(self.workspace, port=value)
        validate_options(self.workspace, port=0)

    def test_output_must_be_inside_workspace(self):
        for target in (self.root / "source" / "tour.mp4", REPO / "tour.mp4", "../tour.mp4", "tour.webm"):
            with self.subTest(case="outside-or-invalid"), self.assertRaises(PipelineError):
                validate_options(self.workspace, target)

    def test_workspace_cannot_overlap_repository(self):
        for root in (REPO, REPO / "output", REPO.parent):
            with self.subTest(case="overlap"), self.assertRaisesRegex(PipelineError, "^E_PATH_OVERLAP$"):
                validate_options(root)

    def test_output_relative_and_nested(self):
        (self.workspace / "videos").mkdir()
        self.assertEqual(validate_options(self.workspace, "videos/tour.mp4")[1], Path("videos/tour.mp4"))

    def test_existing_output_is_never_overwritten(self):
        output = self.workspace / "tour.mp4"
        output.write_bytes(b"original")
        with self.assertRaisesRegex(PipelineError, "^E_VIDEO_OUTPUT_EXISTS$"):
            render_video(self.workspace)
        self.assertEqual(output.read_bytes(), b"original")

    def test_output_symlinks_and_dangling_symlinks_rejected(self):
        for index, target in enumerate((self.workspace / "manifest.json", self.root / "missing")):
            output = self.workspace / f"link-{index}.mp4"
            output.symlink_to(target)
            with self.subTest(case=index), self.assertRaisesRegex(PipelineError, "^E_VIDEO_OUTPUT_EXISTS$"):
                render_video(self.workspace, output)

    def test_symlink_parent_rejected(self):
        (self.workspace / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(PipelineError, "^E_VIDEO_RENDER$"):
            render_video(self.workspace, "alias/tour.mp4")
        self.assertFalse((self.root / "tour.mp4").exists())

    def test_symlink_workspace_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaisesRegex(PipelineError, "^E_VIDEO_RENDER$"):
            render_video(alias)

    def test_missing_ffmpeg_is_actionable_and_lazy(self):
        with patch("ct_education.video.shutil.which", return_value=None), patch("ct_education.video.importlib.import_module") as load:
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_DEPENDENCY_FFMPEG$"):
                _dependencies()
            load.assert_not_called()

    def test_missing_playwright_is_actionable(self):
        with patch("ct_education.video.shutil.which", return_value="ffmpeg"), patch(
            "ct_education.video.importlib.import_module", side_effect=ImportError("synthetic diagnostic")
        ):
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_DEPENDENCY_PLAYWRIGHT$"):
                render_video(self.workspace)
        self.assertFalse((self.workspace / "tour.mp4").exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["workspace"])

    def test_only_exact_loopback_origin_allowed(self):
        origin = "http://127.0.0.1:12345"
        self.assertTrue(_same_origin(origin + "/api/slice?axis=axial&index=0", origin))
        for url in ("https://example.invalid/", "http://localhost:12345/", "http://127.0.0.1:12346/",
                    "http://127.0.0.1:12345" + "@" + "example.invalid/", "http://user" + "@" + "127.0.0.1:12345/",
                    "file:///example", "data:text/plain,test", "ws://127.0.0.1:12345/", "http://[invalid"):
            with self.subTest(url=url):
                self.assertFalse(_same_origin(url, origin))

    def test_mocked_render_private_atomic_output_and_cleanup(self):
        with self.runtime() as (context, page, encoder, server, factory, chromium):
            result = render_video(self.workspace, duration=1, fps=2)
            self.assertEqual(result, {"status": "complete", "frames": 2, "fps": 2, "duration": 1, "width": 1280, "height": 720})
            factory.assert_called_once_with(self.workspace, 0, require_frontend=True)
            server.shutdown.assert_called_once()
            context.close.assert_called_once()
            self.assertEqual(page.screenshot.call_count, 2)
            launch = chromium.launch_persistent_context.call_args
            self.assertNotIn(REPO, Path(launch.args[0]).parents)
            self.assertEqual(launch.kwargs["service_workers"], "block")
            route = MagicMock()
            handler = context.route.call_args.args[1]
            route.request.url, route.request.method = "https://example.invalid/", "GET"
            handler(route)
            route.abort.assert_called_once()
            route.request.url = "http://127.0.0.1:12345/api/manifest"
            handler(route)
            route.continue_.assert_called_once()
            context.route_web_socket.assert_called_once()
        output = self.workspace / "tour.mp4"
        self.assertEqual(output.read_bytes(), b"synthetic-encoded-video")
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["workspace"])

    def test_browser_missing_and_diagnostics_sanitized(self):
        with self.runtime() as (_, _, _, server, _, chromium):
            chromium.launch_persistent_context.side_effect = RuntimeError("synthetic browser diagnostic")
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_BROWSER$"):
                render_video(self.workspace)
            server.shutdown.assert_called_once()
        self.assertFalse((self.workspace / "tour.mp4").exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["workspace"])

    def test_capture_failure_kills_encoder_and_cleans_resources(self):
        with self.runtime() as (context, page, encoder, server, _, _):
            page.screenshot.side_effect = RuntimeError("synthetic browser diagnostic")
            encoder.poll.return_value = None
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_RENDER$"):
                render_video(self.workspace, duration=1, fps=1)
            encoder.kill.assert_called_once()
            context.close.assert_called_once()
            server.shutdown.assert_called_once()
        self.assertFalse((self.workspace / "tour.mp4").exists())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["workspace"])

    def test_failed_encoding_never_publishes(self):
        with self.runtime() as (_, _, encoder, _, _, _):
            encoder.wait.return_value = 1
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_ENCODER$"):
                render_video(self.workspace, duration=1, fps=1)
        self.assertFalse((self.workspace / "tour.mp4").exists())

    def test_output_created_during_capture_is_not_overwritten(self):
        with self.runtime() as (_, page, _, _, _, _):
            image = page.screenshot.return_value

            def capture(**kwargs):
                (self.workspace / "tour.mp4").write_bytes(b"original")
                return image

            page.screenshot.side_effect = capture
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_RENDER$"):
                render_video(self.workspace, duration=1, fps=1)
        self.assertEqual((self.workspace / "tour.mp4").read_bytes(), b"original")

    def test_driver_environment_private_and_restored(self):
        with patch.dict(os.environ, {"DEBUG": "pw:api", "PWDEBUG": "1", "TMPDIR": "synthetic"}):
            with _browser_environment(self.root):
                self.assertEqual(os.environ["TMPDIR"], str(self.root))
                self.assertNotIn("DEBUG", os.environ)
                self.assertNotIn("PWDEBUG", os.environ)
            self.assertEqual(os.environ["TMPDIR"], "synthetic")
            self.assertEqual(os.environ["DEBUG"], "pw:api")
            self.assertEqual(os.environ["PWDEBUG"], "1")

    def test_missing_meshes_fail_instead_of_recording_partial_scene(self):
        with self.runtime() as (_, page, _, _, _, _):
            page.evaluate.side_effect = None
            page.evaluate.return_value = 0
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_ASSETS$"):
                render_video(self.workspace, duration=1, fps=1)
            page.screenshot.assert_not_called()

    def test_failed_asset_request_stops_capture(self):
        with self.runtime() as (_, page, _, _, _, _):
            page.on.side_effect = lambda event, handler: handler(MagicMock()) if event == "requestfailed" else None
            with self.assertRaisesRegex(PipelineError, "^E_VIDEO_ASSETS$"):
                render_video(self.workspace, duration=1, fps=1)
            page.screenshot.assert_not_called()

    def test_capture_uses_seconds_tour_stops_and_source_sweep(self):
        with self.runtime() as (_, page, _, _, _, _):
            self.manifest["tour"].append({"target_ras": [-2, -2, 2]})
            _capture(page, "http://127.0.0.1:12345", self.manifest, io.BytesIO(), 8, 2)
            times = [call.args[1]["seconds"] for call in page.evaluate.call_args_list
                     if len(call.args) == 2 and isinstance(call.args[1], dict) and "seconds" in call.args[1]]
            self.assertEqual(times, [n / 2 for n in range(8)])
            steps = [call.args[1] for call in page.evaluate.call_args_list if "setTourStep" in call.args[0]]
            self.assertEqual(steps, [0, 1])
            slices = [call.args[1][2] for call in page.evaluate.call_args_list if "selectSource" in call.args[0]]
            self.assertGreater(len(set(slices)), 1)

    def test_annotation_tour_does_not_sweep_away_source_selection(self):
        with self.runtime() as (_, page, _, _, _, _):
            self.manifest["annotations"] = [{"id": "candidate-1"}]
            _capture(page, "http://127.0.0.1:12345", self.manifest, io.BytesIO(), 4, 2)
            self.assertFalse(any("selectSource" in call.args[0] for call in page.evaluate.call_args_list))

    def test_cli_defaults_and_sanitized_result(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch("ct_education.video.render_video", return_value={"status": "complete"}) as render:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(main(["render-video", "--workspace", str(self.workspace)]), 0)
            render.assert_called_once_with(str(self.workspace), None, duration=20, fps=15, width=1280, height=720, port=0)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "complete"})
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_bad_arguments_and_dependency_errors_are_generic(self):
        for args, code in ((["--fps", "not-a-number"], "E_ARGUMENTS"),
                           (["--duration", "nan"], "E_VIDEO_DURATION"),
                           (["--fps", "0"], "E_VIDEO_FPS")):
            stderr = io.StringIO()
            with self.subTest(code=code), redirect_stderr(stderr):
                self.assertEqual(main(["render-video", "--workspace", str(self.workspace), *args]), 2)
            self.assertEqual(stderr.getvalue(), code + "\n")
        stderr = io.StringIO()
        with patch("ct_education.video.shutil.which", return_value=None), redirect_stderr(stderr):
            self.assertEqual(main(["render-video", "--workspace", str(self.workspace)]), 2)
        self.assertEqual(stderr.getvalue(), "E_VIDEO_DEPENDENCY_FFMPEG\n")

    @unittest.skipUnless(os.environ.get("CT_EDU_VIDEO_FFMPEG_SMOKE") == "1" and shutil.which("ffmpeg"),
                         "opt-in synthetic ffmpeg smoke")
    def test_real_ffmpeg_synthetic_frames(self):
        with self.runtime(real_encoder=True):
            render_video(self.workspace, duration=1, fps=2, width=32, height=32)
        data = (self.workspace / "tour.mp4").read_bytes()
        self.assertIn(b"ftyp", data)
        self.assertLess(data.index(b"moov"), data.index(b"mdat"))


if __name__ == "__main__":
    unittest.main()
