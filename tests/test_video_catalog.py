"""Two explicitly selected videos; all fixtures and servers are ephemeral."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from unittest.mock import patch

from ct_education.cli import main
from ct_education.safety import PipelineError
from ct_education.server import create_server
from test_video_http import MP4, VideoHTTPFixture


DEMO = {"id": "demo", "title": "Interface demo", "url": "/api/video", "download_url": "/api/video?download=1"}
RENDERED = {"id": "rendered", "title": "Rendered film", "url": "/api/video/rendered", "download_url": "/api/video/rendered?download=1"}


class VideoCatalogTests(VideoHTTPFixture):
    def test_all_catalog_configurations_and_default_urls(self):
        for demo, rendered, versions in ((False, False, []), (True, False, [DEMO]),
                                         (False, True, [RENDERED]), (True, True, [DEMO, RENDERED])):
            with self.subTest(demo=demo, rendered=rendered), self.running(demo, rendered):
                expected = {"available": bool(versions)}
                if versions:
                    expected.update(url=versions[0]["url"], download_url=versions[0]["download_url"], versions=versions)
                self.assertEqual(json.loads(self.request("/api/video-info")[2]), expected)
                for version, enabled, content, filename in (
                    (DEMO, demo, MP4, "ct-education-tour.mp4"),
                    (RENDERED, rendered, MP4[::-1], "ct-education-film.mp4"),
                ):
                    for key, disposition in (("url", "inline"), ("download_url", "attachment")):
                        for method in ("GET", "HEAD"):
                            status, headers, body = self.request(version[key], method)
                            self.assertEqual(status, 200 if enabled else 404)
                            if enabled:
                                self.assertEqual(body, content if method == "GET" else b"")
                                self.assertEqual(headers["Content-Length"], str(len(content)))
                                self.assertEqual(headers["Content-Disposition"], f'{disposition}; filename="{filename}"')

    def test_rendered_ranges_for_get_head_and_download(self):
        content = MP4[::-1]
        size = len(content)
        cases = [("0-0", 0, 0), ("5-17", 5, 17), ("12-", 12, size - 1),
                 ("-9", size - 9, size - 1), ("-9999", 0, size - 1),
                 ("0-9999", 0, size - 1), (f"{size - 1}-", size - 1, size - 1)]
        with self.running(rendered=True):
            for path in (RENDERED["url"], RENDERED["download_url"]):
                for method in ("GET", "HEAD"):
                    for value, start, end in cases:
                        with self.subTest(path=path, method=method, range=value):
                            status, headers, body = self.request(path, method, [("Range", "bytes=" + value)])
                            self.assertEqual(status, 206)
                            self.assertEqual(headers["Content-Range"], f"bytes {start}-{end}/{size}")
                            self.assertEqual(headers["Content-Length"], str(end - start + 1))
                            self.assertEqual(body, content[start:end + 1] if method == "GET" else b"")

    def test_rendered_invalid_ranges_and_empty_file(self):
        invalid = ["", "bytes=", "bytes=-", "bytes=-0", "bytes=9-8", f"bytes={len(MP4)}-",
                   "bytes=0-1,3-4", "items=0-1", "bytes=+1-2", "bytes=1.0-2", "bytes=1--2",
                   "bytes=0 - 1", "bytes=" + "9" * 5000 + "-"]
        with self.running(rendered=True):
            for method in ("GET", "HEAD"):
                for headers in [[("Range", value)] for value in invalid] + [[("Range", "bytes=0-1")] * 2]:
                    status, response, body = self.request(RENDERED["url"], method, headers)
                    self.assertEqual((status, body), (416, b""))
                    self.assertEqual(response["Content-Range"], f"bytes */{len(MP4)}")
            self.rendered.write_bytes(b"")
            self.assertEqual(self.request(RENDERED["url"])[2], b"")
            self.assertEqual(self.request(RENDERED["url"], headers=[("Range", "bytes=0-")])[0], 416)

    def test_rendered_guards_and_no_filename_queries_or_directory_routes(self):
        with self.running(rendered=True):
            denied_headers = [[("Host", "external.invalid")], [("Origin", "https://external.invalid")],
                              [("Origin", "null")], [("Sec-Fetch-Site", "cross-site")],
                              [("Host", f"127.0.0.1:{self.port}")] * 2,
                              [("Origin", f"http://127.0.0.1:{self.port}")] * 2]
            for method in ("GET", "HEAD"):
                for path in (RENDERED["url"], RENDERED["download_url"]):
                    for headers in denied_headers:
                        self.assertEqual(self.request(path, method, headers)[0], 403)
                for path in ("/" + self.rendered_relative, "/videos/", "/api/video/rendered/",
                             "/api/video/rendered/other.mp4", "/api/video/rendered/../other.mp4",
                             "/api/video/%72endered", "/api/video/rendered?file=other.mp4",
                             "/api/video/rendered?download=0", "/api/video/rendered?download=1&download=1",
                             "/api/video/rendered?download=1&file=other.mp4", "/api/video-info?version=rendered"):
                    self.assertIn(self.request(path, method)[0], (400, 404))

    def test_both_flags_share_startup_validation(self):
        (self.workspace / "linked.mp4").symlink_to(self.rendered)
        (self.workspace / "linked").symlink_to(self.rendered.parent, target_is_directory=True)
        (self.workspace / "directory.mp4").mkdir()
        os.mkfifo(self.workspace / "pipe.mp4")
        cases = ["", ".", "missing.mp4", "other.webm", "../other.mp4", "videos/../other.mp4",
                 self.rendered, "bad\x00.mp4", "linked.mp4", "linked/" + self.rendered.name,
                 "directory.mp4", "pipe.mp4"]
        for flag in ("video_file", "rendered_video_file"):
            for selection in cases:
                with self.subTest(flag=flag), self.assertRaisesRegex(PipelineError, "^E_VIDEO_FILE$"):
                    create_server(self.workspace, 0, **{flag: selection})

    def test_rendered_replacement_never_falls_back_to_demo(self):
        with self.running(rendered=True):
            self.rendered.unlink()
            for replacement in ("missing", "symlink", "fifo", "directory"):
                if replacement == "symlink":
                    self.rendered.symlink_to(self.video)
                elif replacement == "fifo":
                    os.mkfifo(self.rendered)
                elif replacement == "directory":
                    self.rendered.mkdir()
                for method in ("GET", "HEAD"):
                    self.assertEqual(self.request(RENDERED["url"], method)[0], 404)
                self.assertEqual(self.request(DEMO["url"])[2], MP4)
                if replacement in ("symlink", "fifo"):
                    self.rendered.unlink()

    def test_rendered_parent_symlink_replacement(self):
        with self.running(False, True):
            moved = self.workspace / "moved"
            self.rendered.parent.rename(moved)
            self.rendered.parent.symlink_to(moved, target_is_directory=True)
            for method in ("GET", "HEAD"):
                self.assertEqual(self.request(RENDERED["url"], method)[0], 404)

    def test_catalog_head_and_changed_file_size(self):
        with self.running(rendered=True):
            _, get_headers, _ = self.request("/api/video-info")
            _, head_headers, _ = self.request("/api/video-info", "HEAD")
            get_headers.pop("Date")
            head_headers.pop("Date")
            self.assertEqual(get_headers, head_headers)
            self.rendered.write_bytes(MP4 * 2)
            status, headers, body = self.request(RENDERED["url"], headers=[("Range", "bytes=-5")])
            self.assertEqual((status, body), (206, MP4[-5:]))
            self.assertEqual(headers["Content-Range"], f"bytes {len(MP4) * 2 - 5}-{len(MP4) * 2 - 1}/{len(MP4) * 2}")

    def test_cli_additive_flags_and_sanitized_failure(self):
        for demo in (None, self.relative):
            with patch("ct_education.cli.create_server") as factory, redirect_stdout(io.StringIO()):
                args = ["serve", "--workspace", str(self.workspace), "--rendered-video-file", self.rendered_relative]
                if demo:
                    args += ["--video-file", demo]
                self.assertEqual(main(args), 0)
                factory.assert_called_once_with(str(self.workspace), 8787, require_frontend=True,
                                                video_file=demo, rendered_video_file=self.rendered_relative)
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(["serve", "--workspace", str(self.workspace),
                                   "--rendered-video-file", "synthetic-missing.mp4"]), 2)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(errors.getvalue(), "E_VIDEO_FILE\n")
