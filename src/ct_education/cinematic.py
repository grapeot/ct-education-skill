"""Offline Blender film preparation; source arrays never receive display transforms."""

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from .safety import REPO, PipelineError, directory_fd, disjoint, local_file, read_json, write_json
from .server import validate_manifest
from .candidate_geometry import extract_candidate


SHOT_BOUNDARIES = (0, 3, 6.5, 11.5, 14.5, 18, 24, 28, 33, 36)
ORBIT_KNOTS = ((0, 0, 0), (0.2, 130, 60), (0.55, 155, 60),
               (0.8, 335, 500), (0.9, 360, 0), (1, 360, 0))


def ease(value):
    x = min(1.0, max(0.0, value))
    return x * x * x * (x * (x * 6 - 15) + 10)


def orbit_angle(u):
    """Unwrapped radians; shared Hermite tangents preserve the approved C1 beat."""
    u = min(1.0, max(0.0, u))
    for (a, y0, m0), (b, y1, m1) in zip(ORBIT_KNOTS, ORBIT_KNOTS[1:]):
        if u <= b:
            h, x = b - a, (u - a) / (b - a)
            degrees = ((2 * x**3 - 3 * x**2 + 1) * y0
                       + (x**3 - 2 * x**2 + x) * h * m0
                       + (-2 * x**3 + 3 * x**2) * y1
                       + (x**3 - x**2) * h * m1)
            return math.radians(degrees)


def sweep_progress(seconds):
    """A 1.5-second traverse with smooth velocity ramps, then a half-second hold."""
    x = min(1.5, max(0.0, seconds))
    ramp = 0.2
    if x < ramp:
        q = x / ramp
        return ramp * (q**3 - 0.5 * q**4) / (1.5 - ramp)
    if x > 1.5 - ramp:
        q = (1.5 - x) / ramp
        return 1 - ramp * (q**3 - 0.5 * q**4) / (1.5 - ramp)
    return (x - ramp / 2) / (1.5 - ramp)


def nice_mm(width):
    target = width * 0.22
    power = 10 ** math.floor(math.log10(target))
    return max(v * power for v in (0.1, 0.2, 0.5, 1, 2, 5) if v * power <= target)


def source_plane(volume, affine, axis, index, crop=None, window=(-600, 1500)):
    """Return one shared screen-basis image and pixel-center mapping in RAS mm."""
    a = np.asarray(affine, dtype=float)
    axes = {'axial': (0, 0, 1, 2), 'coronal': (1, 0, 2, 1), 'sagittal': (2, 1, 2, 0)}
    array_axis, col, row, fixed = axes[axis]
    raw = np.take(volume, index, axis=array_axis)
    reverse = axis != 'axial' and a[2, row] > 0
    if reverse:
        raw = raw[::-1]
    h, w = raw.shape
    x0, y0, x1, y1 = crop or (0, 0, w, h)
    if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
        raise PipelineError('E_CINEMATIC_CROP')
    # Compute the footprint before local cropping so zoom does not select a tiny
    # dense island and erase the surrounding source evidence.
    components, count = ndimage.label(raw > -500)
    sizes = np.bincount(components.ravel())
    if count:
        sizes[0] = 0
        footprint = ndimage.binary_fill_holes(components == sizes.argmax())
    else:
        footprint = np.ones(raw.shape, bool)
    footprint = footprint[y0:y1, x0:x1]
    raw = raw[y0:y1, x0:x1]
    right = a[:3, col]
    down = a[:3, row] * (-1 if reverse else 1)
    if abs(np.dot(right, down)) > 1e-5 * np.linalg.norm(right) * np.linalg.norm(down):
        raise PipelineError('E_CINEMATIC_SHEARED_GRID')
    ijk = np.zeros(3)
    ijk[fixed] = index
    ijk[col] = x0
    ijk[row] = h - 1 - y0 if reverse else y0
    origin = (a @ np.r_[ijk, 1])[:3]
    spacing = np.array([np.linalg.norm(right), np.linalg.norm(down)])
    u, v = right / spacing[0], -down / spacing[1]
    normal = np.cross(u, v)
    center = origin + right * (raw.shape[1] - 1) / 2 + down * (raw.shape[0] - 1) / 2
    full_center = origin + right * ((w - 1) / 2 - x0) + down * ((h - 1) / 2 - y0)
    wc, ww = window
    pixels = np.clip((raw.astype(float) - (wc - ww / 2)) * 255 / ww, 0, 255).astype('uint8')
    rgba = np.dstack([pixels, pixels, pixels, footprint.astype('uint8') * 255])
    names = ['R', 'A', 'S']
    opposite = ['L', 'P', 'I']
    def direction(vec):
        dominant = int(np.argmax(np.abs(vec)))
        return (names if vec[dominant] > 0 else opposite)[dominant] if abs(vec[dominant]) > 0.95 else 'source'
    state = dict(axis=axis, index=int(index), origin_ras=origin.tolist(), center_ras=center.tolist(),
                 u=u.tolist(), v=v.tolist(), normal=normal.tolist(), source_affine=a.tolist(),
                 pixel_right_ras=right.tolist(), pixel_down_ras=down.tolist(),
                 spacing_mm=spacing.tolist(), crop=[x0, y0, x1, y1],
                 size_mm=[raw.shape[1] * spacing[0], raw.shape[0] * spacing[1]],
                 full_size_mm=[w * spacing[0], h * spacing[1]],
                 full_center_ras=full_center.tolist(),
                 image_size=[raw.shape[1], raw.shape[0]], window=list(window),
                 orientation=[direction(-u), direction(u), direction(v), direction(-v)])
    return rgba, state


def frame_state(volume, manifest, seconds):
    if not math.isfinite(seconds) or not 0 <= seconds <= 36:
        raise PipelineError('E_CINEMATIC_TIME')
    # First halve the reference timeline; local authored tracks stay inside its windows.
    raw_seconds = 2 * seconds
    shot = min(8, int(np.searchsorted(SHOT_BOUNDARIES, seconds, side='right')) - 1)
    shape = np.array(volume.shape)
    axis, fraction = 'axial', 0.5
    title, note = 'THE SOURCE IMAGE', 'CT images are reconstructed from X-ray projections.'
    visibility = dict(bones=0.0, lungs=0.0, airways=0.0, vessels=0.0)
    orbit, face, cut, zoom = 0.0, 1.0, False, 1.0
    show_plane = True
    stack = 0.0
    stack_entries = [0.0] * 7
    stack_opacity, plane_opacity, stack_framing = 0.0, 1.0, 0.0
    branch_emphasis = 0.0
    camera_elevation = 0.35
    depth_view, outro_progress = False, 0.0
    inspection_scale, marker_opacity = 1.0, 1.0
    window = (-600, 1500)
    if raw_seconds < 6:
        camera_elevation = -0.35
        face = 1 - ease((raw_seconds - 2) / 4) * 0.75
    elif raw_seconds < 13:
        title, note = 'IMAGES INTO SPACE', 'Representative subset; gaps exaggerated, then restored. Not acquisition footage.'
        reveal = ease((seconds - 5.5) / 1)
        camera_elevation = -0.35 + 0.7 * reveal
        face = 0.25 * (1 - reveal)
        stack = 1 - ease((seconds - 4.8) / 0.7)
        stack_entries[3] = 1.0
        for rank, index in enumerate((2, 4, 1, 5, 0, 6)):
            stack_entries[index] = ease((seconds - 3.15 - rank * 0.2) / 0.4)
        stack_opacity = plane_opacity = 1 - reveal
        stack_framing = ease((seconds - 3) / 0.55) * (1 - reveal)
        visibility.update(lungs=0.15 * reveal, bones=reveal, airways=reveal, vessels=0.7 * reveal)
    elif raw_seconds < 23:
        title, note = 'ONE SPATIAL OVERVIEW', 'Surfaces are heuristic display derivatives, not source-image evidence.'
        orbit, face = orbit_angle((seconds - 6.5) / 5), 0
        visibility.update(lungs=0.15, bones=1, airways=1, vessels=0.7)
        show_plane = False
    elif raw_seconds < 29:
        title, note = 'DENSE STRUCTURE', 'Bone candidates establish context; surrounding surfaces gently recede.'
        face = 0
        orbit = 2 * math.pi + 0.12 * ease((seconds - 11.5) / 2)
        visibility.update(bones=1, lungs=0.15 * (1 - ease((seconds - 11.5) / 2)))
        window = (450, 2000)
    elif raw_seconds < 36:
        title, note = 'AIRSPACES AND BRANCHES', 'Envelope, airway and dense vascular candidates; identity and completeness unverified.'
        face = 0
        branch_emphasis = ease((seconds - 14.5) / 0.6)
        orbit = math.radians(130 + 25 * ease((seconds - 14.5) / 3.5))
        visibility.update(lungs=0.08 * (1 - branch_emphasis), airways=1, vessels=1,
                          bones=0.15 * (1 - branch_emphasis))
        show_plane = False
    elif raw_seconds < 48:
        segment = min(2, int((seconds - 18) // 2))
        axis = ['axial', 'coronal', 'sagittal'][segment]
        fraction = 0.25 + 0.5 * sweep_progress((seconds - 18) % 2)
        title, note = 'ONE PLANE, TWO VIEWS', 'Same source image and physical plane. Colored surfaces are not CT interiors.'
        face, cut = 0.15, True
        visibility.update(lungs=0.22, bones=0.7, airways=1, vessels=0.7)
    elif raw_seconds < 56:
        title, note = 'THE TWO VIEWS AGREE', 'Face-on inspection matches orientation and physical framing.'
        axis, fraction = 'sagittal', 0.75
        face, cut = 0.15 + 0.85 * ease((seconds - 24.5) / 1.5), True
        fade = 1 - ease((seconds - 24) / 1)
        visibility.update(lungs=0.22 * fade, bones=0.7 * fade, airways=fade, vessels=0.7 * fade)
    else:
        title, note = 'N1 / LOCAL SOURCE EVIDENCE', 'Localized region; boundary unverified. Same N1 location in both views.'
        depth_view, face, show_plane, plane_opacity = True, 0.0, False, 0.0
        inspection_scale = 1 - 0.6 * ease((seconds - 28) / 2)
        outro_progress = ease((seconds - 30) / 5.5)
        full_width_mm = shape[2] * np.linalg.norm(np.asarray(manifest['affine_ras'])[:3, 0])
        zoom = max(1.0, float(full_width_mm / (100 * inspection_scale)))
    ai = {'axial': 0, 'coronal': 1, 'sagittal': 2}[axis]
    index = round((shape[ai] - 1) * fraction)
    candidate = manifest['annotations'][0] if manifest['annotations'] else None
    crop = None
    if 28 <= seconds <= 36 and candidate:
        ijk = (np.linalg.inv(np.array(manifest['affine_ras'])) @ np.r_[candidate['position_ras'], 1])[:3]
        index = int(np.clip(round(ijk[2]), 0, shape[0] - 1))
        width, height = int(shape[2]), int(shape[1])
        cw, ch = min(width, max(8, round(width / zoom))), min(height, max(8, round(height / zoom)))
        x = int(np.clip(round(ijk[0] - cw / 2), 0, width - cw))
        y = int(np.clip(round(ijk[1] - ch / 2), 0, height - ch))
        crop = (x, y, x + cw, y + ch)
    elif 28 <= seconds:
        title, note = 'SOURCE DETAIL', 'No candidate supplied. Inspecting source image only.'
        depth_view, face, show_plane, plane_opacity = False, 1.0, True, 1.0
    rgba, plane = source_plane(volume, manifest['affine_ras'], axis, index, crop, window)
    return rgba, dict(plane=plane, time=seconds, raw_time=raw_seconds, shot=shot + 1,
                      title=title, note=note, visibility=visibility, zoom=zoom,
                      orbit=orbit, face=face, clip=cut, show_plane=show_plane, stack=stack,
                      stack_entries=stack_entries, stack_opacity=stack_opacity, stack_framing=stack_framing,
                      plane_opacity=plane_opacity, branch_emphasis=branch_emphasis, camera_elevation=camera_elevation,
                      depth_view=depth_view, outro_progress=outro_progress, inspection_scale=inspection_scale,
                      marker_opacity=marker_opacity, left_ruler_visible=True,
                      locator=candidate if 28 <= seconds <= 36 else None,
                      display_offsets_ras={}, ruler_mm=nice_mm(plane['size_mm'][0]))


def prepare_candidate(output, volume, manifest):
    """Persist only external candidate evidence and physically mapped local slices."""
    if not manifest['annotations']:
        return None
    annotation = manifest['annotations'][0]
    result = extract_candidate(volume, manifest['affine_ras'], annotation['position_ras'])
    folder = output / 'candidate'
    folder.mkdir(mode=0o700)
    write_json(output, 'candidate/validation.json', result['report'])
    np.save(folder / 'mask.npy', result['mask'])
    np.save(folder / 'roi_hu.npy', result['hu'])
    for threshold, mask in result['masks'].items():
        np.save(folder / f'mask_{threshold}.npy', mask)
    mesh_path = None
    if result['mesh']:
        mesh_path = 'candidate/surface.json'
        write_json(output, mesh_path, result['mesh'])
    density_path = None
    if result['density_mesh']:
        density_path = 'candidate/density_surface.json'
        write_json(output, density_path, result['density_mesh'])
    write_json(output, 'candidate/density_display.json', result['density_display'])
    ijk = (np.linalg.inv(result['affine_ras']) @ np.r_[annotation['position_ras'], 1])[:3]
    planes = []
    for axis, component in [('axial', 2), ('coronal', 1), ('sagittal', 0)]:
        image, plane = source_plane(result['hu'], result['affine_ras'], axis, int(np.floor(ijk[component] + 0.5)))
        # A local evidence window retains all native pixels, not a body-mask selection.
        image[:, :, 3] = 255
        path = f'candidate/{axis}.png'
        Image.fromarray(image).save(output / path)
        planes.append(dict(plane=plane, image=path))
    return dict(status=result['report']['status'], mesh=mesh_path, density_mesh=density_path,
                density_display=result['density_display'], planes=planes,
                center_ras=annotation['position_ras'], half_extent_mm=result['report']['half_extent_mm'],
                locator_half_mm=max(4, annotation['radius_mm'] * 1.5), validation='candidate/validation.json')


def candidate_caption(geometry):
    if geometry and geometry['density_mesh']:
        return f"CT density surface at {geometry['density_display']['threshold_hu']:g} HU; not a verified nodule boundary."
    return 'Localized region; boundary unverified. Same N1 location in both views.'


def render_cinematic(workspace, output, *, blender='blender', duration=36, start=0,
                     fps=24, width=1280, height=720, samples=16, budget=600):
    if (not all(math.isfinite(v) for v in (duration, start, budget)) or not 0 < duration <= 36
            or not 0 <= start <= 36 - duration or not 1 <= fps <= 30
            or not 640 <= width <= 1920 or width % 2 or not 360 <= height <= 1080
            or height % 2 or not 1 <= samples <= 128 or not 10 <= budget <= 1800):
        raise PipelineError('E_CINEMATIC_OPTIONS')
    original_output = Path(output).expanduser().absolute()
    if '..' in original_output.parts:
        raise PipelineError('E_PATH_INVALID')
    original_workspace = Path(workspace).expanduser().absolute()
    _, workspace, output = disjoint(REPO, original_workspace, original_output)
    if original_workspace != workspace:
        raise PipelineError('E_PATH_INVALID')
    if original_output != output or output.exists():
        raise PipelineError('E_CINEMATIC_OUTPUT')
    executable = shutil.which(blender)
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    if not all((executable, ffmpeg, ffprobe)):
        raise PipelineError('E_CINEMATIC_DEPENDENCY')
    manifest = read_json(workspace, 'manifest.json')
    validate_manifest(manifest)
    with local_file(workspace, 'volume.npy') as stream:
        volume = np.load(stream, allow_pickle=False)
    if list(volume.shape) != manifest['shape'] or volume.dtype != np.float32:
        raise PipelineError('E_VOLUME_FORMAT')
    volume.flags.writeable = False
    with directory_fd(output.parent) as parent:
        os.mkdir(output.name, mode=0o700, dir_fd=parent)
    for name in ('textures', 'left', 'frames', 'meshes'):
        (output / name).mkdir(mode=0o700)
    center = (np.array(manifest['bounds_ras']['min']) + np.array(manifest['bounds_ras']['max'])) / 2
    layers = []
    for layer in manifest['layers']:
        with local_file(workspace, layer['mesh']) as stream:
            mesh = json.load(stream)
        with local_file(output, layer['mesh'], 'wb') as stream:
            stream.write(json.dumps(mesh).encode())
        layers.append(layer['id'])
    states = []
    for i in range(math.ceil(duration * fps)):
        rgba, state = frame_state(volume, manifest, start + i / fps)
        Image.fromarray(rgba).save(output / 'textures' / f'{i:05d}.png')
        state['image'] = f'textures/{i:05d}.png'
        states.append(state)
    # Separate representative source planes for the explicitly illustrative stack.
    stack_planes = []
    for i, index in enumerate(np.linspace(0.2, 0.8, 7) * (volume.shape[0] - 1)):
        rgba, plane = source_plane(volume, manifest['affine_ras'], 'axial', round(index))
        Image.fromarray(rgba).save(output / 'textures' / f'stack_{i}.png')
        stack_planes.append(dict(plane=plane, image=f'textures/stack_{i}.png'))
    candidate_geometry = prepare_candidate(output, volume, manifest)
    config = dict(schema=5, center_ras=center.tolist(), bounds_ras=manifest['bounds_ras'], layers=layers, frames=states,
                  candidate_geometry=candidate_geometry,
                  label_grid=read_json(workspace, 'labels-grid.json'), stack=stack_planes,
                  colors=dict(bones=[0.66, 0.60, 0.48, 1], lungs=[0.08, 0.32, 0.34, 1],
                              airways=[0.34, 0.69, 0.70, 1], vessels=[0.53, 0.23, 0.14, 1]),
                  width=width, height=height, fps=fps, samples=samples)
    write_json(output, 'state.json', config)
    shutil.copyfile(Path(__file__).with_name('cinematic_blender.py'), output / 'generate_scene.py')
    started = time.monotonic()
    try:
        with local_file(output, 'render.log', 'wb') as log:
            subprocess.run([executable, '-b', '--factory-startup', '--python-exit-code', '1',
                            '-P', str(output / 'generate_scene.py'), '--', str(output)],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=budget)
    except (subprocess.SubprocessError, OSError):
        raise PipelineError('E_CINEMATIC_RENDER') from None
    return finish_cinematic(output, config, started=started)


def finish_cinematic(output, config, *, started=None):
    """Finalize an already rendered, trusted run without repeating Blender work."""
    _, output = disjoint(REPO, output)
    if (output / 'film.mp4').exists():
        raise PipelineError('E_CINEMATIC_OUTPUT')
    started = time.monotonic() if started is None else started
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise PipelineError('E_CINEMATIC_DEPENDENCY')
    states = config['frames']
    width, height, fps = config['width'], config['height'], config['fps']
    compose_frames(output, config)
    with local_file(output, 'encode.log', 'wb') as log:
        subprocess.run([ffmpeg, '-v', 'error', '-n', '-framerate', str(fps), '-i',
                        str(output / 'frames' / '%05d.png'), '-c:v', 'libx264', '-crf', '18',
                        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-map_metadata', '-1',
                        str(output / 'film.mp4')], stdout=log, stderr=log, check=True, timeout=120)
        subprocess.run([ffmpeg, '-v', 'error', '-i', str(output / 'film.mp4'), '-f', 'null', '-'],
                       stdout=log, stderr=log, check=True, timeout=120)
    result = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json',
                             str(output / 'film.mp4')], capture_output=True, check=True, timeout=30)
    probe = json.loads(result.stdout)
    stream = probe['streams'][0]
    if (int(stream['nb_frames']) != len(states) or stream['width'] != width or stream['height'] != height
            or stream['r_frame_rate'] != f'{fps}/1'
            or abs(float(stream['duration']) - len(states) / fps) > 1 / fps):
        raise PipelineError('E_CINEMATIC_VALIDATION')
    validation = dict(status='complete', frames=len(states), fps=fps, width=width, height=height,
                      duration=len(states) / fps, full_decode=True, elapsed_seconds=round(time.monotonic() - started, 2),
                      motion_review='pending continuous playback', source='individual Blender frames; no interpolation')
    write_json(output, 'probe.json', probe)
    write_json(output, 'validation.json', validation)
    return validation


def compose_frames(output, config):
    width, height = config['width'], config['height']
    pw, ph = width // 2 - 36, height - 180
    expected = {f'{i:05d}.png' for i in range(len(config['frames']))}
    if {p.name for p in (output / 'left').glob('*.png')} != expected:
        raise PipelineError('E_CINEMATIC_FRAMES')
    font = ImageFont.load_default(size=max(13, width // 70))
    heading = ImageFont.load_default(size=max(20, width // 43))
    for i, state in enumerate(config['frames']):
        canvas = Image.new('RGB', (width, height), '#0b111b')
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 20), state['title'], font=heading, fill='#efe9dc')
        draw.text((24, 64), '01  /  SPATIAL CONTEXT', font=font, fill='#8eb8bc')
        draw.text((width // 2 + 12, 64), '02  /  SOURCE CT', font=font, fill='#8eb8bc')
        with Image.open(output / 'left' / f'{i:05d}.png') as left:
            left.load()
            if left.size != (pw, ph):
                raise PipelineError('E_CINEMATIC_FRAMES')
            canvas.paste(left.convert('RGB'), (24, 92))
        plane = state['plane']
        mw, mh = plane['size_mm']
        scale = min(pw / mw, ph / mh) * 0.86
        rw, rh = round(mw * scale), round(mh * scale)
        scale_x, scale_y = rw / mw, rh / mh
        rx, ry = width // 2 + 12 + (pw - rw) // 2, 92 + (ph - rh) // 2
        with Image.open(output / state['image']) as raw:
            # Both views use the identical HU RGB; footprint transparency is shared.
            raw = raw.resize((rw, rh), Image.Resampling.BILINEAR)
            canvas.paste(raw, (rx, ry), raw)
        length = state['ruler_mm']
        y = min(92 + ph - 18, ry + rh + 8)
        draw.line((rx, y, rx + length * scale_x, y), fill='#0b111b', width=5)
        draw.line((rx, y, rx + length * scale_x, y), fill='#d6bb83', width=2)
        right_text = f'{length:g} mm'
        label_y = y - font.size - 6
        draw.rectangle((rx - 3, label_y - 3, rx + draw.textlength(right_text, font=font) + 3, y - 2), fill='#0b111b')
        draw.text((rx, label_y), right_text, font=font, fill='#e1cfa8')
        with open(output / 'left' / f'{i:05d}.json') as stream:
            projection = json.load(stream)
        a, b = projection['ruler_pixels']
        if state['face'] == 1:
            if (abs(np.linalg.norm(np.array(b) - a) - length * scale_x) > 1
                    or not np.allclose(projection['camera_right'], plane['u'], atol=1e-5)
                    or not np.allclose(projection['camera_up'], plane['v'], atol=1e-5)):
                raise PipelineError('E_CINEMATIC_FACE_MATCH')
        if state['left_ruler_visible']:
            draw.line((24 + a[0], 92 + a[1], 24 + b[0], 92 + b[1]), fill='#0b111b', width=5)
            draw.line((24 + a[0], 92 + a[1], 24 + b[0], 92 + b[1]), fill='#d6bb83', width=2)
            text = f'{length:g} mm / in slice plane'
            tx = max(24, min(24 + a[0], 24 + pw - draw.textlength(text, font=font)))
            ty = max(92, min(92 + a[1] - font.size - 8, 92 + ph - font.size - 8))
            if not state['show_plane'] or state['depth_view']:
                tx, ty = 24, 92 + ph - font.size - 8
            else:
                for _ in range(3):
                    if any(tx < 24 + p[0] + font.size and tx + draw.textlength(text, font=font) > 24 + p[0]
                           and ty < 92 + p[1] + font.size and ty + font.size + 4 > 92 + p[1]
                           for p in projection['orientation_pixels']):
                        ty = max(92, ty - font.size - 12)
            draw.rectangle((tx - 2, ty - 2, tx + draw.textlength(text, font=font) + 3, ty + font.size + 4), fill='#0b111b')
            draw.text((tx, ty), text, font=font, fill='#e1cfa8')
        labels = plane['orientation']
        positions = [(rx + 4, ry + rh / 2), (rx + rw - font.size - 4, ry + rh / 2), (rx + rw / 2, ry + 3)]
        tagged = list(zip(labels[:3], positions))
        tagged += [(label, (24 + p[0], 92 + p[1])) for label, p in
                   zip(labels[:3] if state['show_plane'] else [], projection['orientation_pixels'])]
        for label, point in tagged:
            box = draw.textbbox(point, label, font=font)
            draw.rectangle((box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2), fill='#0b111b')
            draw.text(point, label, font=font, fill='#d8e3e4')
        if state['locator']:
            delta = np.array(state['locator']['position_ras']) - np.array(plane['center_ras'])
            right_point = (rx + rw / 2 + np.dot(delta, plane['u']) * scale_x,
                           ry + rh / 2 - np.dot(delta, plane['v']) * scale_y)
            point = projection['locator_pixels']
            geometry = config['candidate_geometry']
            half_mm = geometry['locator_half_mm']
            markers = [(24 + point[0], 92 + point[1], half_mm * pw / (projection['field_width_m'] * 1000), 24),
                       (*right_point, half_mm * scale_x, width // 2 + 12)]
            for px, py, radius, panel_x in markers:
                radius = max(24, radius + 8)
                if not (panel_x <= px <= panel_x + pw and 92 <= py <= 92 + ph):
                    raise PipelineError('E_CINEMATIC_LOCATOR_OFFSCREEN')
                arm = min(24, radius * 0.3)
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        x, y = px + sx * radius, py + sy * radius
                        line = [(x - sx * arm, y), (x, y), (x, y - sy * arm)]
                        draw.line(line, fill='#080b12', width=8)
                        draw.line(line, fill='#dab2ff', width=4)
                label = 'N1 / nodule candidate'
                label_width = draw.textlength(label, font=font)
                lx = max(panel_x + 8, min(px + radius + 24, panel_x + pw - label_width - 12))
                ly = max(100, py - radius - font.size - 32)
                line = [(lx + 8, ly + font.size + 6), (px + radius + 12, py - radius - 12), (px + radius, py - radius)]
                draw.line(line, fill='#080b12', width=6)
                draw.line(line, fill='#e8d8ff', width=2)
                draw.rectangle((lx - 5, ly - 4, lx + label_width + 5, ly + font.size + 5), fill='#0b111b')
                draw.text((lx, ly), label, font=font, fill='#dab2ff')
        draw.text((width // 2 + 12, height - 79), f"{plane['axis'].upper()} / {plane['window'][0]:g} : {plane['window'][1]:g} HU window", font=font, fill='#a6b5c2')
        # Wrap captions based on measured width, rather than allowing small-frame overflow.
        note = state['note']
        if state['depth_view'] and config['candidate_geometry']:
            note = candidate_caption(config['candidate_geometry'])
        words, lines, line = note.split(), [], ''
        for word in words:
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=font) > width - 48 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        draw.multiline_text((24, height - 50), '\n'.join(lines), font=font, fill='#bbc5ce', spacing=3)
        canvas.save(output / 'frames' / f'{i:05d}.png')
        with Image.open(output / 'frames' / f'{i:05d}.png') as saved:
            if saved.size != (width, height):
                raise PipelineError('E_CINEMATIC_FRAMES')
            saved.verify()
    if {p.name for p in (output / 'frames').glob('*.png')} != expected:
        raise PipelineError('E_CINEMATIC_FRAMES')
