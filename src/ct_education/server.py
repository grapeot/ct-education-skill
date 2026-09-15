"""Guarded loopback HTTP routes; no arbitrary workspace or repository serving."""

from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mmap
import os
from pathlib import Path
import re
import stat
from urllib.parse import parse_qs, urlsplit

import numpy as np
from PIL import Image

from .safety import REPO, PipelineError, boundaries, local_file, read_json
from .segmentation import LAYER_INFO


STATIC = re.compile(r"/assets/[A-Za-z0-9_-]+-[A-Za-z0-9_-]{8,}\.(js|css|woff2|svg)")
MIME = {"js": "text/javascript", "css": "text/css", "woff2": "font/woff2", "svg": "image/svg+xml"}


def validate_manifest(manifest):
    expected = {"schema_version", "shape", "spacing", "affine_lps", "affine_ras", "bounds_ras", "layers", "annotations", "warnings", "source", "tour"}
    try:
        if set(manifest) != expected or manifest["schema_version"] != 1:
            raise ValueError
        shape = manifest["shape"]
        if len(shape) != 3 or any(type(n) is not int or n < 2 for n in shape) or np.prod(shape, dtype=object) > 600_000_000:
            raise ValueError
        affine = np.asarray(manifest["affine_lps"], dtype=float)
        ras = np.asarray(manifest["affine_ras"], dtype=float)
        if affine.shape != (4, 4) or ras.shape != (4, 4) or not np.isfinite(affine).all() or not np.isfinite(ras).all():
            raise ValueError
        if not np.array_equal(affine[3], [0, 0, 0, 1]) or abs(np.linalg.det(affine[:3, :3])) < 1e-8:
            raise ValueError
        if not np.allclose(ras, np.diag([-1, -1, 1, 1]) @ affine):
            raise ValueError
        if manifest["source"] != {"modality": "CT", "slice_count": shape[0]}:
            raise ValueError
        layer_ids = set()
        for layer in manifest["layers"]:
            name = layer["id"]
            if name not in LAYER_INFO or name in layer_ids or layer["mesh"] != f"meshes/{name}.json":
                raise ValueError
            if set(layer) != {"id", "name", "color", "description", "review_status", "mesh"} or layer["review_status"] != "algorithmic candidate":
                raise ValueError
            layer_ids.add(name)
        # Reject nonfinite values anywhere, not just in the spatial transform.
        json.dumps(manifest, allow_nan=False)
        return affine, ras, layer_ids
    except (KeyError, TypeError, ValueError, OverflowError):
        raise PipelineError("E_WORKSPACE_MANIFEST") from None


def render_slice(volume, axis, index, wc, ww):
    axes = {"axial": 0, "coronal": 1, "sagittal": 2}
    if axis not in axes or not 0 <= index < volume.shape[axes[axis]]:
        raise ValueError
    if not np.isfinite([wc, ww]).all() or ww <= 0 or ww > 100_000 or abs(wc) > 100_000:
        raise ValueError
    plane = np.take(volume, index, axis=axes[axis])
    pixels = np.clip((plane.astype(np.float32) - (wc - ww / 2)) * (255 / ww), 0, 255).astype(np.uint8)
    output = io.BytesIO()
    Image.fromarray(pixels).save(output, format="PNG")
    return output.getvalue()


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def server_close(self):
        super().server_close()
        if hasattr(self, "resources"):
            self.resources.close()

    def handle_error(self, request, client_address):
        pass


def create_server(workspace, port=8787, require_frontend=False, *, video_file=None, rendered_video_file=None):
    _, workspace = boundaries(workspace=workspace)
    videos = {}
    versions = []
    for selected, identifier, title, url, filename in (
        (video_file, "demo", "Interface demo", "/api/video", "ct-education-tour.mp4"),
        (rendered_video_file, "rendered", "Rendered film", "/api/video/rendered", "ct-education-film.mp4"),
    ):
        if selected is None:
            continue
        try:
            selected = Path(selected)
            if selected.is_absolute() or ".." in selected.parts or selected.suffix.lower() != ".mp4":
                raise ValueError
            with local_file(workspace, selected) as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0:
                    raise ValueError
        except (OSError, PipelineError, TypeError, ValueError):
            raise PipelineError("E_VIDEO_FILE") from None
        videos[url] = (selected, filename)
        versions.append({"id": identifier, "title": title, "url": url, "download_url": url + "?download=1"})
    frontend = REPO / "frontend" / "dist"
    if require_frontend and not (frontend / "index.html").is_file():
        raise PipelineError("E_FRONTEND_NOT_BUILT")
    resources = ExitStack()
    try:
        manifest = read_json(workspace, "manifest.json")
        affine, affine_ras, layer_ids = validate_manifest(manifest)
        source = resources.enter_context(local_file(workspace, "volume.npy"))
        version = np.lib.format.read_magic(source)
        if version == (1, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_1_0(source)
        elif version == (2, 0):
            shape, fortran, dtype = np.lib.format.read_array_header_2_0(source)
        else:
            raise PipelineError("E_VOLUME_FORMAT")
        offset = source.tell()
        if list(shape) != manifest["shape"] or fortran or dtype != np.dtype(np.float32):
            raise PipelineError("E_VOLUME_FORMAT")
        mapped = resources.enter_context(mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ))
        if len(mapped) != offset + int(np.prod(shape)) * 4:
            raise PipelineError("E_VOLUME_FORMAT")
        volume = np.ndarray(shape, dtype=dtype, buffer=mapped, offset=offset)
        manifest_bytes = json.dumps(manifest, allow_nan=False).encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            server_version = "CTEducation"
            sys_version = ""

            def setup(self):
                super().setup()
                self.connection.settimeout(10)

            def log_message(self, format, *args):
                pass

            def send_error(self, code, message=None, explain=None):
                self.respond(code, b'{"error":"E_REQUEST"}', "application/json")

            def respond(self, code, body, content_type, index=None, *, length=None, headers=()):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body) if length is None else length))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self'; connect-src 'self'; worker-src 'none'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
                if index is not None:
                    self.send_header("X-Slice-Index", str(index))
                for name, value in headers:
                    self.send_header(name, value)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def serve_video(self, selected, filename, download):
                with local_file(workspace, selected) as stream:
                    metadata = os.fstat(stream.fileno())
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 0:
                        raise PipelineError("E_VIDEO_FILE")
                    size = metadata.st_size
                    disposition = "attachment" if download else "inline"
                    headers = [("Accept-Ranges", "bytes"),
                               ("Content-Disposition", f'{disposition}; filename="{filename}"')]
                    start, end, code = 0, size - 1, 200
                    ranges = self.headers.get_all("Range", [])
                    if ranges:
                        try:
                            if len(ranges) != 1:
                                raise ValueError
                            match = re.fullmatch(r"bytes=([0-9]*)-([0-9]*)", ranges[0])
                            if not match or not any(match.groups()) or size == 0:
                                raise ValueError
                            first, last = match.groups()
                            if first:
                                start = int(first)
                                end = min(int(last), size - 1) if last else size - 1
                                if start >= size or end < start:
                                    raise ValueError
                            else:
                                suffix = int(last)
                                if suffix == 0:
                                    raise ValueError
                                start = max(0, size - suffix)
                            code = 206
                            headers.append(("Content-Range", f"bytes {start}-{end}/{size}"))
                        except ValueError:
                            self.respond(416, b"", "video/mp4",
                                         headers=headers + [("Content-Range", f"bytes */{size}")])
                            return
                    length = end - start + 1
                    stream.seek(start)
                    # Bound reads to the advertised length, including if the file grows.
                    try:
                        self.respond(code, b"", "video/mp4", length=length, headers=headers)
                        if self.command != "HEAD":
                            remaining = length
                            while remaining:
                                chunk = stream.read(min(64 * 1024, remaining))
                                if not chunk:
                                    self.close_connection = True
                                    return
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                    except OSError:
                        # Headers are already sent; never append an error to video bytes.
                        self.close_connection = True

            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                try:
                    port_number = self.server.server_address[1]
                    hosts = {f"localhost:{port_number}", f"127.0.0.1:{port_number}", f"[::1]:{port_number}"}
                    if port_number == 80:
                        hosts.update({"localhost", "127.0.0.1", "[::1]"})
                    host_headers = self.headers.get_all("Host", [])
                    origins = self.headers.get_all("Origin", [])
                    if len(host_headers) != 1 or host_headers[0] not in hosts:
                        self.send_error(403)
                        return
                    if len(origins) > 1 or (origins and origins[0] not in {"http://" + host for host in hosts}):
                        self.send_error(403)
                        return
                    if self.headers.get("Sec-Fetch-Site") == "cross-site":
                        self.send_error(403)
                        return
                    parsed = urlsplit(self.path)
                    path = parsed.path
                    if parsed.scheme or parsed.netloc or parsed.fragment or "%" in path or "\\" in path or ".." in path or "//" in path:
                        self.send_error(400)
                        return
                    query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=8)
                    if any(len(values) != 1 for values in query.values()):
                        raise ValueError
                    boundaries(workspace=workspace)
                    if path == "/api/manifest" and not query:
                        self.respond(200, manifest_bytes, "application/json")
                    elif path == "/api/video-info" and not query:
                        info = {"available": bool(versions)}
                        if versions:
                            info.update(url=versions[0]["url"], download_url=versions[0]["download_url"], versions=versions)
                        self.respond(200, json.dumps(info).encode(), "application/json")
                    elif path in videos:
                        if query not in ({}, {"download": ["1"]}):
                            raise ValueError
                        self.serve_video(*videos[path], download=bool(query))
                    elif path.startswith("/api/mesh/") and not query:
                        name = path.removeprefix("/api/mesh/")
                        if name not in layer_ids:
                            self.send_error(404)
                            return
                        with local_file(workspace, f"meshes/{name}.json") as stream:
                            self.respond(200, stream.read(), "application/json")
                    elif path == "/api/slice":
                        if set(query) - {"axis", "index", "wc", "ww"} or not {"axis", "index"} <= query.keys():
                            raise ValueError
                        index = int(query["index"][0])
                        body = render_slice(volume, query["axis"][0], index, float(query.get("wc", [-600])[0]), float(query.get("ww", [1500])[0]))
                        self.respond(200, body, "image/png", index=index)
                    elif path == "/api/voxel":
                        if set(query) != {"i", "j", "k"}:
                            raise ValueError
                        i, j, k = [int(query[key][0]) for key in ("i", "j", "k")]
                        if not (0 <= i < shape[2] and 0 <= j < shape[1] and 0 <= k < shape[0]):
                            raise ValueError
                        point = np.array([i, j, k, 1])
                        result = {"hu": float(volume[k, j, i]), "lps": (affine @ point)[:3].tolist(), "ras": (affine_ras @ point)[:3].tolist()}
                        self.respond(200, json.dumps(result, allow_nan=False).encode(), "application/json")
                    elif path in ("/", "/index.html") and not query:
                        with local_file(frontend, "index.html") as stream:
                            self.respond(200, stream.read(), "text/html; charset=utf-8")
                    elif STATIC.fullmatch(path) and not query:
                        with local_file(frontend, path.lstrip("/")) as stream:
                            self.respond(200, stream.read(), MIME[path.rsplit(".", 1)[1]])
                    else:
                        self.send_error(404)
                except (ValueError, KeyError, TypeError, OverflowError):
                    self.send_error(400)
                except (OSError, PipelineError):
                    self.send_error(404)
                except Exception:
                    self.send_error(500)

        if not 0 <= port <= 65535:
            raise PipelineError("E_PORT")
        server = ViewerServer(("127.0.0.1", port), Handler)
        server.resources = resources
        return server
    except BaseException:
        resources.close()
        raise
