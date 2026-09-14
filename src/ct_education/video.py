"""Optional deterministic recording of the source-linked local browser scene."""

from contextlib import contextmanager
import importlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

from .safety import PipelineError, boundaries, directory_fd, disjoint, local_file, read_json
from .server import create_server, validate_manifest


def validate_options(workspace, output=None, *, duration=20, fps=15, width=1280, height=720, port=0):
    if type(duration) not in (int, float) or not math.isfinite(duration) or not 0 < duration <= 120:
        raise PipelineError("E_VIDEO_DURATION")
    if type(fps) is not int or not 1 <= fps <= 60:
        raise PipelineError("E_VIDEO_FPS")
    if any(type(n) is not int or n < 2 or n % 2 for n in (width, height)) or width > 1920 or height > 1080:
        raise PipelineError("E_VIDEO_DIMENSIONS")
    if type(port) is not int or not 0 <= port <= 65535:
        raise PipelineError("E_PORT")
    _, root = boundaries(workspace=workspace)
    # Do not resolve away symlinks before the descriptor-relative checks.
    original = Path(workspace).expanduser().absolute()
    with directory_fd(original):
        pass
    target = Path(output).expanduser() if output is not None else root / "tour.mp4"
    if not target.is_absolute():
        target = root / target
    if ".." in target.parts or target.suffix.lower() != ".mp4":
        raise PipelineError("E_VIDEO_OUTPUT")
    try:
        relative = target.relative_to(root)
    except ValueError:
        raise PipelineError("E_VIDEO_OUTPUT") from None
    with directory_fd(target.parent) as parent:
        try:
            os.stat(target.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise PipelineError("E_VIDEO_OUTPUT_EXISTS")
    return root, relative, math.ceil(duration * fps)


def _dependencies():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PipelineError("E_VIDEO_DEPENDENCY_FFMPEG")
    try:
        playwright = importlib.import_module("playwright.sync_api")
    except ImportError:
        raise PipelineError("E_VIDEO_DEPENDENCY_PLAYWRIGHT") from None
    return ffmpeg, playwright.sync_playwright


def _same_origin(url, origin):
    try:
        parsed, expected = urlsplit(url), urlsplit(origin)
        return (parsed.scheme == "http" and parsed.netloc == expected.netloc
                and parsed.hostname == "127.0.0.1" and parsed.port == expected.port
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


@contextmanager
def _browser_environment(stage):
    # The Playwright driver also creates artifacts and can inherit debug logging.
    keys = ("TMPDIR", "TMP", "TEMP", "DEBUG", "PWDEBUG")
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            if key in ("DEBUG", "PWDEBUG"):
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(stage)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _capture(page, origin, manifest, stream, frame_count, fps):
    failed = []
    page.on("requestfailed", lambda request: failed.append(True))
    page.on("response", lambda response: failed.append(True)
            if response.status >= 400 and urlsplit(response.url).path != "/favicon.ico" else None)
    page.on("pageerror", lambda error: failed.append(True))
    page.goto(origin, wait_until="networkidle", timeout=120_000)
    page.wait_for_function("window.ctEducation && window.ctEducation.ready === true", timeout=120_000)
    page.evaluate("async () => { await document.fonts.ready; window.ctEducation.setScripted(true); }")
    if page.evaluate("window.ctEducation.meshCount") != len(manifest["layers"]):
        raise PipelineError("E_VIDEO_ASSETS")
    bounds = manifest["bounds_ras"]
    center = [(a + b) / 2 for a, b in zip(bounds["min"], bounds["max"])]
    diagonal = math.dist(bounds["min"], bounds["max"])
    radius = max(diagonal * 1.15, 40)
    height = max((bounds["max"][2] - bounds["min"][2]) * 0.22, 12)
    tour_length = page.evaluate("window.ctEducation.tourLength")
    if type(tour_length) is not int or not 0 <= tour_length <= 256:
        raise PipelineError("E_VIDEO_ASSETS")
    previous_step, previous_slice = -1, None
    previous_target, target = center, center
    step_start = 0
    for frame in range(frame_count):
        seconds = frame / fps
        step = min(tour_length - 1, frame * tour_length // frame_count)
        if step != previous_step:
            page.evaluate("index => window.ctEducation.setTourStep(index)", step)
            selected = page.evaluate("window.ctEducation.getSelection()?.ras")
            previous_target, target = target, selected or center
            previous_step, step_start = step, frame
        # Without user annotations, compare native slices rather than only orbiting.
        if not manifest["annotations"]:
            nz, ny, nx = manifest["shape"]
            fraction = 0.5 - 0.3 * math.sin(2 * math.pi * frame / max(frame_count - 1, 1))
            k = round((nz - 1) * fraction)
            if k != previous_slice:
                page.evaluate("p => window.ctEducation.selectSource(...p)", [(nx - 1) // 2, (ny - 1) // 2, k])
                previous_slice = k
        blend = min(1, (frame - step_start) / fps)
        blend = blend * blend * (3 - 2 * blend)
        orbit_target = [a + (b - a) * blend for a, b in zip(previous_target, target)]
        page.evaluate("""p => {
            window.ctEducation.setOrbit(p.orbit);
            window.ctEducation.renderFrame(p.seconds);
        }""", {"orbit": {"target": orbit_target, "radius": radius, "height": height}, "seconds": seconds})
        if failed:
            raise PipelineError("E_VIDEO_ASSETS")
        stream.write(page.screenshot(type="png", full_page=False, animations="disabled", timeout=120_000))


def render_video(workspace, output=None, *, duration=20, fps=15, width=1280, height=720, port=0):
    """Publish a new owner-only MP4; never overwrite or expose browser diagnostics."""
    try:
        root, relative, frame_count = validate_options(workspace, output, duration=duration,
                                                       fps=fps, width=width, height=height, port=port)
        ffmpeg, sync_playwright = _dependencies()
        manifest = read_json(root, "manifest.json")
        validate_manifest(manifest)
        with directory_fd(root) as root_fd, directory_fd(root.parent) as parent_fd:
            with tempfile.TemporaryDirectory(prefix=".ct-edu-video-", dir=root.parent) as temporary:
                stage = Path(temporary)
                boundaries(workspace=stage)
                disjoint(root, stage)
                stage_identity = stage.stat()

                def check():
                    if boundaries(workspace=workspace)[1] != root:
                        raise PipelineError("E_PATH_CHANGED")
                    for path, fd in ((root, root_fd), (root.parent, parent_fd)):
                        with directory_fd(path) as current:
                            if not os.path.samestat(os.fstat(current), os.fstat(fd)):
                                raise PipelineError("E_PATH_CHANGED")
                    with directory_fd(stage) as current:
                        if not os.path.samestat(os.fstat(current), stage_identity):
                            raise PipelineError("E_PATH_CHANGED")

                check()
                with create_server(root, port, require_frontend=True) as server:
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        origin = f"http://127.0.0.1:{server.server_address[1]}"
                        with _browser_environment(stage), sync_playwright() as playwright:
                            try:
                                context = playwright.chromium.launch_persistent_context(
                                    str(stage / "profile"), headless=True,
                                    viewport={"width": width, "height": height}, device_scale_factor=1,
                                    reduced_motion="reduce", service_workers="block", accept_downloads=False,
                                    env={**{k: v for k, v in os.environ.items() if k not in ("DEBUG", "PWDEBUG")},
                                         "TMPDIR": str(stage), "TMP": str(stage), "TEMP": str(stage)},
                                    args=["--disable-background-networking", "--disable-component-update",
                                          "--disable-sync", "--no-first-run", "--no-proxy-server",
                                          "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"],
                                )
                            except Exception:
                                raise PipelineError("E_VIDEO_BROWSER") from None
                            try:
                                context.route("**/*", lambda route: route.continue_()
                                              if _same_origin(route.request.url, origin) and route.request.method in ("GET", "HEAD")
                                              else route.abort())
                                context.route_web_socket("**/*", lambda socket: socket.close())
                                with local_file(stage, "tour.mp4", "w+b") as encoded:
                                    # Faststart must reopen an independent file description on macOS;
                                    # /dev/fd duplicates share offsets there and corrupt the relocation.
                                    check()
                                    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                                               "-f", "image2pipe", "-framerate", str(fps), "-vcodec", "png", "-i", "pipe:0",
                                               "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                                               "-movflags", "+faststart", "-map_metadata", "-1", "-f", "mp4",
                                               str(stage / "tour.mp4")]
                                    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                                          stderr=subprocess.DEVNULL) as encoder:
                                        try:
                                            _capture(context.new_page(), origin, manifest, encoder.stdin, frame_count, fps)
                                            encoder.stdin.close()
                                            if encoder.wait(timeout=120) != 0:
                                                raise PipelineError("E_VIDEO_ENCODER")
                                        finally:
                                            if encoder.poll() is None:
                                                encoder.kill()
                                                encoder.wait()
                                    if os.fstat(encoded.fileno()).st_size == 0:
                                        raise PipelineError("E_VIDEO_ENCODER")
                                    check()
                                    with local_file(stage, "tour.mp4") as current:
                                        if not os.path.samestat(os.fstat(current.fileno()), os.fstat(encoded.fileno())):
                                            raise PipelineError("E_PATH_CHANGED")
                            finally:
                                context.close()
                    finally:
                        server.shutdown()
                        thread.join()
                check()
                # Hard-link publication is atomic and exclusive, including against symlink races.
                with local_file(stage, "tour.mp4") as encoded, directory_fd(stage) as stage_fd:
                    with directory_fd(root / relative.parent) as destination_fd:
                        check()
                        os.link("tour.mp4", relative.name, src_dir_fd=stage_fd,
                                dst_dir_fd=destination_fd, follow_symlinks=False)
                return {"status": "complete", "frames": frame_count, "fps": fps,
                        "duration": frame_count / fps, "width": width, "height": height}
    except PipelineError:
        raise
    except Exception:
        raise PipelineError("E_VIDEO_RENDER") from None
