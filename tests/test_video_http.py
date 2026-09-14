"""Opt-in video HTTP tests using only synthetic, external temporary fixtures."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from ct_education.cli import main
from ct_education.safety import REPO, PipelineError, disjoint, local_file, write_json
from ct_education.server import create_server


MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + bytes(range(256))


class VideoHTTPTests(unittest.TestCase):
    def setUp(self):
        base = Path(tempfile.gettempdir()).resolve()
        if base == REPO or REPO in base.parents:
            self.fail("external-temp-required")
        temporary = tempfile.TemporaryDirectory(prefix="ct-edu-http-test-", dir=base)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        disjoint(REPO, self.root)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(mode=0o700)
        self.relative = "videos/synthetic-source-name.mp4"
        self.video = self.workspace / self.relative
        self.video.parent.mkdir()
        self.video.write_bytes(MP4)
        (self.workspace / "other.mp4").write_bytes(b"synthetic-hidden-video")
        (self.workspace / "provenance.json").write_bytes(b"synthetic-hidden-provenance")
        self.manifest = {
            "schema_version": 1, "shape": [2, 2, 2], "spacing": [1, 1, 1],
            "affine_lps": np.eye(4).tolist(),
            "affine_ras": np.diag([-1, -1, 1, 1]).tolist(),
            "bounds_ras": {"min": [-1.5, -1.5, -0.5], "max": [0.5, 0.5, 1.5]},
            "layers": [{"id": "lungs", "name": "Synthetic", "color": "#65c8cc",
                        "description": "Synthetic", "review_status": "algorithmic candidate",
                        "mesh": "meshes/lungs.json"}],
            "annotations": [], "warnings": [], "source": {"modality": "CT", "slice_count": 2},
            "tour": [],
        }
        write_json(self.workspace, "manifest.json", self.manifest)
        np.save(self.workspace / "volume.npy", np.zeros((2, 2, 2), dtype=np.float32))
        (self.workspace / "meshes").mkdir()
        write_json(self.workspace, "meshes/lungs.json", {"positions": [], "indices": []})
        self.static_repo = self.root / "generic-app"
        static = self.static_repo / "frontend" / "dist"
        (static / "assets").mkdir(parents=True)
        (static / "index.html").write_text("<html>Synthetic viewer</html>")
        (static / "assets" / "index-12345678.js").write_text("export const synthetic = true;")

    @contextmanager
    def running(self, enabled=True):
        with patch("ct_education.server.REPO", self.static_repo):
            server = create_server(self.workspace, 0, True,
                                   video_file=self.relative if enabled else None)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        self.port = server.server_address[1]
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def request(self, path="/api/video", method="GET", headers=()):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest(method, path, skip_host=True)
            if not any(name.lower() == "host" for name, _ in headers):
                connection.putheader("Host", f"127.0.0.1:{self.port}")
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders()
            response = connection.getresponse()
            body = response.read()
            result = dict(response.getheaders())
            self.assertEqual(result["Cache-Control"], "no-store")
            self.assertEqual(result["X-Content-Type-Options"], "nosniff")
            self.assertEqual(result["Referrer-Policy"], "no-referrer")
            self.assertEqual(result["Cross-Origin-Resource-Policy"], "same-origin")
            for directive in ("media-src 'self'", "frame-ancestors 'none'", "object-src 'none'",
                              "connect-src 'self'", "worker-src 'none'", "base-uri 'none'"):
                self.assertIn(directive, result["Content-Security-Policy"])
            self.assertNotIn("Access-Control-Allow-Origin", result)
            self.assertNotIn("Transfer-Encoding", result)
            self.assertNotIn(self.video.name, str(result))
            self.assertNotIn(str(self.root), str(result))
            self.assertNotIn(b"synthetic-hidden", body)
            if method == "HEAD":
                self.assertEqual(body, b"")
            else:
                self.assertEqual(int(result["Content-Length"]), len(body))
            if response.status >= 400:
                self.assertIn(body, (b"", b'{"error":"E_REQUEST"}'))
            return response.status, result, body
        finally:
            connection.close()

    def test_off_by_default(self):
        with self.running(enabled=False):
            self.assertEqual(json.loads(self.request("/api/video-info")[2]), {"available": False})
            for method in ("GET", "HEAD"):
                for path in ("/api/video", "/api/video?download=1", "/other.mp4", "/" + self.relative):
                    self.assertEqual(self.request(path, method)[0], 404)
        with create_server(self.workspace, 0) as server:
            self.assertEqual(server.server_address[0], "127.0.0.1")

    def test_info_contains_only_generic_urls(self):
        with self.running():
            status, _, body = self.request("/api/video-info")
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body), {"available": True, "url": "/api/video",
                                               "download_url": "/api/video?download=1"})
            self.assertNotIn(self.video.name.encode(), body)
            self.assertNotIn(str(self.root).encode(), body)

    def test_full_inline_and_download(self):
        with self.running():
            for query, disposition in (("", "inline"), ("?download=1", "attachment")):
                status, headers, body = self.request("/api/video" + query)
                self.assertEqual((status, body), (200, MP4))
                self.assertEqual(headers["Content-Type"], "video/mp4")
                self.assertEqual(headers["Accept-Ranges"], "bytes")
                self.assertNotIn("Content-Range", headers)
                self.assertEqual(headers["Content-Disposition"],
                                 f'{disposition}; filename="ct-education-tour.mp4"')

    def test_bounded_open_and_suffix_ranges(self):
        size = len(MP4)
        cases = [("0-0", 0, 0), ("5-17", 5, 17), ("12-", 12, size - 1),
                 ("-9", size - 9, size - 1), ("-9999", 0, size - 1),
                 ("0-9999", 0, size - 1), (f"{size - 1}-", size - 1, size - 1),
                 ("0002-0003", 2, 3)]
        with self.running():
            for value, start, end in cases:
                for method in ("GET", "HEAD"):
                    with self.subTest(range=value, method=method):
                        status, headers, body = self.request(method=method, headers=[("Range", "bytes=" + value)])
                        self.assertEqual(status, 206)
                        self.assertEqual(headers["Content-Range"], f"bytes {start}-{end}/{size}")
                        self.assertEqual(int(headers["Content-Length"]), end - start + 1)
                        self.assertEqual(body, MP4[start:end + 1] if method == "GET" else b"")

    def test_download_supports_ranges(self):
        with self.running():
            status, headers, body = self.request("/api/video?download=1", headers=[("Range", "bytes=1-5")])
            self.assertEqual((status, body), (206, MP4[1:6]))
            self.assertEqual(headers["Content-Disposition"], 'attachment; filename="ct-education-tour.mp4"')

    def test_invalid_unsatisfiable_and_multiple_ranges(self):
        cases = ["bytes=", "bytes=-", "bytes=-0", "bytes=9-8", f"bytes={len(MP4)}-",
                 "bytes=9999-10000", "bytes=0-1,3-4", "items=0-1", "bytes=+1-2",
                 "bytes=1.0-2", "bytes=one-two", "bytes=0 - 1", "bytes=1--2",
                 "bytes=" + "9" * 5000 + "-", ""]
        with self.running():
            for value in cases:
                for method in ("GET", "HEAD"):
                    with self.subTest(range=value[:40], method=method):
                        status, headers, body = self.request(method=method, headers=[("Range", value)])
                        self.assertEqual((status, body), (416, b""))
                        self.assertEqual(headers["Content-Range"], f"bytes */{len(MP4)}")
                        self.assertEqual(headers["Content-Length"], "0")
            status, headers, body = self.request(headers=[("Range", "bytes=0-1"), ("Range", "bytes=2-3")])
            self.assertEqual((status, body), (416, b""))
            self.assertEqual(headers["Content-Range"], f"bytes */{len(MP4)}")

    def test_empty_regular_mp4(self):
        self.video.write_bytes(b"")
        with self.running():
            for method in ("GET", "HEAD"):
                self.assertEqual(self.request(method=method)[0], 200)
                status, headers, body = self.request(method=method, headers=[("Range", "bytes=0-")])
                self.assertEqual((status, body), (416, b""))
                self.assertEqual(headers["Content-Range"], "bytes */0")

    def test_head_metadata_matches_get_for_all_routes(self):
        paths = ["/api/video", "/api/video?download=1", "/api/video-info", "/api/manifest",
                 "/api/mesh/lungs", "/api/slice?axis=axial&index=0", "/api/voxel?i=0&j=0&k=0",
                 "/", "/index.html", "/assets/index-12345678.js", "/missing"]
        with self.running():
            for path in paths:
                with self.subTest(route=path):
                    get_status, get_headers, _ = self.request(path)
                    head_status, head_headers, _ = self.request(path, "HEAD")
                    self.assertEqual(get_status, head_status)
                    get_headers.pop("Date")
                    head_headers.pop("Date")
                    self.assertEqual(get_headers, head_headers)

    def test_host_origin_and_fetch_guards(self):
        with self.running():
            cases = [[("Host", "external.invalid")], [("Origin", "https://external.invalid")],
                     [("Origin", "null")], [("Origin", f"http://127.0.0.1:{self.port + 1}")],
                     [("Sec-Fetch-Site", "cross-site")],
                     [("Host", f"127.0.0.1:{self.port}")] * 2,
                     [("Origin", f"http://127.0.0.1:{self.port}")] * 2]
            for path in ("/api/video", "/api/video?download=1", "/api/video-info"):
                for method in ("GET", "HEAD"):
                    for headers in cases:
                        self.assertEqual(self.request(path, method, headers)[0], 403)
                self.assertEqual(self.request(path, headers=[("Origin", f"http://localhost:{self.port}")])[0], 200)

    def test_paths_queries_and_hidden_files_are_not_exposed(self):
        paths = ["/other.mp4", "/" + self.relative, "/videos/", "/provenance.json", "/volume.npy",
                 "/labels.npy", "/.env", "/.git/config", "/api/video/other.mp4", "/api/video/",
                 "/api/video/../other.mp4", "/api/%76ideo", "/api//video", "/api\\video",
                 "/api/video?file=other.mp4", "/api/video?download=0", "/api/video?download=",
                 "/api/video?download=1&download=1", "/api/video?download=1&file=other.mp4",
                 "/api/video-info?file=other.mp4", "/api/video?download", "/api/video#fragment",
                 "http://external.invalid/api/video"]
        with self.running():
            for path in paths:
                for method in ("GET", "HEAD"):
                    with self.subTest(route=path, method=method):
                        self.assertIn(self.request(path, method)[0], (400, 404))
            self.assertEqual(json.loads(self.request("/api/manifest")[2]), self.manifest)

    def test_startup_rejects_invalid_or_missing_video(self):
        targets = ["missing.mp4", "", ".", "other.webm", "../other.mp4", "videos/../other.mp4",
                   self.video, self.root / "outside.mp4", "videos/missing.mp4", "bad\x00.mp4"]
        for target in targets:
            with self.subTest(case="invalid-selection"), self.assertRaisesRegex(PipelineError, "^E_VIDEO_FILE$"):
                create_server(self.workspace, 0, video_file=target)

    def test_startup_rejects_symlink_file_and_parent(self):
        (self.workspace / "link.mp4").symlink_to(self.video)
        (self.workspace / "linked").symlink_to(self.video.parent, target_is_directory=True)
        (self.workspace / "outside.mp4").symlink_to(self.root / "missing.mp4")
        for target in ("link.mp4", "linked/" + self.video.name, "outside.mp4"):
            with self.subTest(case="symlink"), self.assertRaisesRegex(PipelineError, "^E_VIDEO_FILE$"):
                create_server(self.workspace, 0, video_file=target)

    def test_startup_rejects_nonregular_files_without_blocking(self):
        (self.workspace / "directory.mp4").mkdir()
        os.mkfifo(self.workspace / "pipe.mp4")
        for target in ("directory.mp4", "pipe.mp4"):
            with self.subTest(case=target), self.assertRaisesRegex(PipelineError, "^E_VIDEO_FILE$"):
                create_server(self.workspace, 0, video_file=target)

    def test_file_symlink_replacement_after_startup(self):
        with self.running():
            self.video.unlink()
            self.video.symlink_to(self.workspace / "other.mp4")
            for method in ("GET", "HEAD"):
                self.assertEqual(self.request(method=method)[0], 404)

    def test_parent_symlink_replacement_after_startup(self):
        with self.running():
            moved = self.workspace / "moved"
            self.video.parent.rename(moved)
            self.video.parent.symlink_to(moved, target_is_directory=True)
            self.assertEqual(self.request()[0], 404)

    def test_missing_or_nonregular_replacement_after_startup(self):
        with self.running():
            self.video.unlink()
            self.assertEqual(self.request()[0], 404)
            os.mkfifo(self.video)
            self.assertEqual(self.request()[0], 404)
            self.video.unlink()
            self.video.mkdir()
            self.assertEqual(self.request()[0], 404)

    def test_current_file_size_is_used_after_changes(self):
        with self.running():
            for content in (MP4[:24], MP4 * 3):
                self.video.write_bytes(content)
                status, headers, body = self.request(headers=[("Range", "bytes=-5")])
                self.assertEqual((status, body), (206, content[-5:]))
                self.assertEqual(headers["Content-Range"], f"bytes {len(content) - 5}-{len(content) - 1}/{len(content)}")
                self.assertEqual(self.request()[2], content)

    def test_stream_reads_are_bounded_even_if_file_grows(self):
        content = MP4 * 1000
        self.video.write_bytes(content)
        reads = []

        @contextmanager
        def tracked_file(root, relative, mode="rb"):
            with local_file(root, relative, mode) as stream:
                if Path(relative) != Path(self.relative):
                    yield stream
                    return
                wrapped = Mock(wraps=stream)

                def read(length):
                    self.assertGreater(length, 0)
                    self.assertLessEqual(length, 64 * 1024)
                    reads.append(length)
                    chunk = stream.read(length)
                    if len(reads) == 1:
                        with self.video.open("ab") as writer:
                            writer.write(b"synthetic-hidden-growth")
                    return chunk

                wrapped.read.side_effect = read
                yield wrapped

        with self.running(), patch("ct_education.server.local_file", tracked_file):
            self.assertEqual(self.request()[2], content)
            self.assertGreater(len(reads), 1)
            reads.clear()
            status, headers, _ = self.request(method="HEAD")
            self.assertEqual(status, 200)
            self.assertEqual(int(headers["Content-Length"]), self.video.stat().st_size)
            self.assertEqual(reads, [])

    def test_cli_optional_flag_and_default(self):
        for selection in (None, self.relative):
            with patch("ct_education.cli.create_server") as factory, redirect_stdout(io.StringIO()):
                args = ["serve", "--workspace", str(self.workspace), "--port", "8787"]
                if selection is not None:
                    args.extend(["--video-file", selection])
                self.assertEqual(main(args), 0)
                factory.assert_called_once_with(str(self.workspace), 8787, require_frontend=True, video_file=selection)

    def test_cli_missing_video_fails_startup_without_private_error(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = main(["serve", "--workspace", str(self.workspace), "--video-file", "synthetic-missing.mp4"])
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "E_VIDEO_FILE\n")


if __name__ == "__main__":
    unittest.main()
