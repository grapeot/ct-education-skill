import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ct_education.cinematic import (SHOT_BOUNDARIES, ORBIT_KNOTS, ease, frame_state,
                                    nice_mm, orbit_angle, render_cinematic, source_plane, sweep_progress)
from ct_education.cli import main
from ct_education.safety import PipelineError, REPO


class CinematicTests(unittest.TestCase):
    def setUp(self):
        self.volume = np.arange(5 * 6 * 7, dtype=np.float32).reshape(5, 6, 7)
        self.affine = np.diag([-0.7, -0.9, 2.0, 1.0])
        self.manifest = dict(affine_ras=self.affine.tolist(), annotations=[])

    def test_native_axial_pixel_basis_and_no_mutation(self):
        original = self.volume.copy()
        rgba, plane = source_plane(self.volume, self.affine, 'axial', 2, window=(100, 400))
        self.assertEqual(rgba.shape, (6, 7, 4))
        np.testing.assert_allclose(plane['origin_ras'], [0, 0, 4])
        np.testing.assert_allclose(plane['u'], [-1, 0, 0])
        np.testing.assert_allclose(plane['v'], [0, 1, 0])
        self.assertEqual(plane['orientation'], ['R', 'L', 'A', 'P'])
        np.testing.assert_array_equal(self.volume, original)

    def test_coronal_superior_up_and_asymmetric_pixels(self):
        rgba, plane = source_plane(self.volume, self.affine, 'coronal', 2, window=(100, 400))
        np.testing.assert_allclose(plane['origin_ras'], [0, -1.8, 8])
        np.testing.assert_allclose(plane['v'], [0, 0, 1])
        expected = np.clip((self.volume[::-1, 2, :] + 100) * 255 / 400, 0, 255).astype('uint8')
        np.testing.assert_array_equal(rgba[:, :, 0], expected)

    def test_sagittal_pixel_roundtrip(self):
        _, plane = source_plane(self.volume, self.affine, 'sagittal', 3)
        p = np.array(plane['origin_ras']) + 2 * np.array(plane['pixel_right_ras']) + np.array(plane['pixel_down_ras'])
        ijk = np.linalg.inv(self.affine) @ np.r_[p, 1]
        np.testing.assert_allclose(ijk, [3, 2, 3, 1])

    def test_crop_uses_pixel_centers_and_actual_physical_extent(self):
        _, plane = source_plane(self.volume, self.affine, 'axial', 1, (2, 1, 6, 5))
        np.testing.assert_allclose(plane['origin_ras'], [-1.4, -0.9, 2])
        np.testing.assert_allclose(plane['size_mm'], [2.8, 3.6])
        np.testing.assert_allclose(plane['center_ras'], [-2.45, -2.25, 2])
        full = source_plane(self.volume, self.affine, 'axial', 1)[1]
        np.testing.assert_allclose(plane['full_center_ras'], full['center_ras'])
        np.testing.assert_allclose(plane['full_size_mm'], full['size_mm'])

    def test_sheared_source_plane_fails_closed(self):
        self.affine[0, 2] = 0.3
        with self.assertRaisesRegex(PipelineError, 'SHEARED'):
            source_plane(self.volume, self.affine, 'coronal', 1)

    def test_easing_has_holds_and_nonuniform_velocity(self):
        self.assertEqual(ease(-1), 0)
        self.assertEqual(ease(2), 1)
        self.assertLess(ease(0.1), 0.02)
        self.assertGreater(ease(0.6) - ease(0.5), ease(0.1) - ease(0))

    def test_single_turn_returns_to_rest_direction(self):
        _, start = frame_state(self.volume, self.manifest, 6.5)
        _, end = frame_state(self.volume, self.manifest, 11)
        self.assertEqual(start['orbit'], 0)
        self.assertAlmostEqual(end['orbit'], 2 * np.pi)

    def test_sweeps_change_axis_without_mutating_source(self):
        for time, expected in [(18.5, 'axial'), (20.5, 'coronal'), (22.5, 'sagittal')]:
            _, state = frame_state(self.volume, self.manifest, time)
            self.assertEqual(state['plane']['axis'], expected)
            self.assertTrue(state['clip'])

    def test_face_on_hold_and_missing_candidate_truth(self):
        _, state = frame_state(self.volume, self.manifest, 27)
        self.assertEqual(state['face'], 1)
        _, state = frame_state(self.volume, self.manifest, 31)
        self.assertIsNone(state['locator'])
        self.assertIn('No candidate', state['note'])

    def test_nice_scale_changes_with_crop(self):
        self.assertEqual(nice_mm(400), 50)
        self.assertEqual(nice_mm(40), 5)

    def test_options_fail_before_any_io(self):
        for options in [dict(duration=float('nan')), dict(duration=36.01), dict(start=1),
                        dict(start=-1), dict(width=641), dict(budget=9999)]:
            with self.assertRaisesRegex(PipelineError, 'OPTIONS'):
                render_cinematic('unused', 'unused', **options)

    def test_repository_output_and_nested_input_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(PipelineError, 'OVERLAP'):
                render_cinematic(root, REPO / 'uncreated')
            with self.assertRaisesRegex(PipelineError, 'OVERLAP'):
                render_cinematic(root, Path(root) / 'uncreated')

    def test_symlink_input_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root).resolve()
            (root / 'source').mkdir()
            (root / 'alias').symlink_to(root / 'source', target_is_directory=True)
            with self.assertRaisesRegex(PipelineError, 'PATH_INVALID'):
                render_cinematic(root / 'alias', root / 'new')
            (root / 'existing').mkdir()
            with self.assertRaisesRegex(PipelineError, 'OUTPUT'):
                render_cinematic(root / 'source', root / 'existing')

    def test_cli_additive_defaults_and_sanitized_errors(self):
        out, err = io.StringIO(), io.StringIO()
        with patch('ct_education.cinematic.render_cinematic', return_value={'status': 'complete'}) as render:
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(['render-cinematic', '--workspace', 'source', '--output', 'new']), 0)
            self.assertEqual(render.call_args.kwargs['start'], 0)
            self.assertEqual(render.call_args.kwargs['duration'], 36)
            self.assertEqual(render.call_args.kwargs['fps'], 24)
        with patch('ct_education.cinematic.render_cinematic', side_effect=RuntimeError('private source')):
            with contextlib.redirect_stderr(err):
                self.assertEqual(main(['render-cinematic', '--workspace', 'source', '--output', 'new']), 2)
        self.assertEqual(err.getvalue().strip(), 'E_OPERATION_FAILED')

    def test_exact_36_second_frame_schedule_and_shot_boundaries(self):
        expected = [0, 72, 156, 276, 348, 432, 576, 672, 792, 864]
        self.assertEqual([int(t * 24) for t in SHOT_BOUNDARIES], expected)
        states = [frame_state(self.volume, self.manifest, i / 24)[1] for i in range(864)]
        self.assertEqual(len(states), 864)
        self.assertLess(states[-1]['time'], 36)
        for shot, (start, end) in enumerate(zip(expected, expected[1:]), 1):
            self.assertEqual({s['shot'] for s in states[start:end]}, {shot})
        for state in states:
            self.assertEqual(state['raw_time'], state['time'] * 2)
        with self.assertRaisesRegex(PipelineError, 'TIME'):
            frame_state(self.volume, self.manifest, 36.001)

    def test_orbit_exact_knots_shared_velocities_and_no_overshoot(self):
        eps = 1e-6
        for u, degrees, slope in ORBIT_KNOTS:
            self.assertAlmostEqual(np.degrees(orbit_angle(u)), degrees, places=8)
            if 0 < u < 1:
                left = np.degrees(orbit_angle(u) - orbit_angle(u - eps)) / eps
                right = np.degrees(orbit_angle(u + eps) - orbit_angle(u)) / eps
                self.assertAlmostEqual(left, slope, delta=0.05)
                self.assertAlmostEqual(right, slope, delta=0.05)
        angles = np.array([orbit_angle(u) for u in np.linspace(0, 1, 2001)])
        self.assertGreaterEqual(np.diff(angles).min(), -1e-12)
        self.assertGreaterEqual(angles.min(), 0)
        self.assertLessEqual(angles.max(), 2 * np.pi + 1e-12)

    def test_fast_slow_fast_contrast_and_settled_orbit_hold(self):
        speed = lambda a, b: (orbit_angle(b) - orbit_angle(a)) / (b - a)
        calm = speed(0.2, 0.55)
        self.assertGreater(speed(0, 0.2), calm * 5)
        self.assertGreater(speed(0.55, 0.8), calm * 5)
        for u in np.linspace(0.9, 1, 20):
            self.assertAlmostEqual(orbit_angle(u), 2 * np.pi)

    def test_staged_stack_entry_is_monotone_and_restored_before_reveal(self):
        states = [frame_state(self.volume, self.manifest, t)[1] for t in np.linspace(3, 5.5, 61)]
        counts = [sum(entry > 0 for entry in s['stack_entries']) for s in states]
        self.assertEqual(counts[0], 1)
        self.assertEqual(counts[-1], 7)
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(set(counts), set(range(1, 8)))
        self.assertEqual(states[-1]['stack'], 0)
        self.assertEqual(states[-1]['stack_entries'], [1] * 7)
        self.assertEqual(states[-1]['visibility']['bones'], 0)

    def test_sweeps_have_steady_interior_and_exact_half_second_holds(self):
        delta = 0.01
        speeds = [(sweep_progress(t + delta) - sweep_progress(t)) / delta for t in (0.4, 0.8, 1.1)]
        np.testing.assert_allclose(speeds, speeds[0], atol=1e-12)
        for t in np.linspace(1.5, 2, 20):
            self.assertEqual(sweep_progress(t), 1)
        for start in (18, 20, 22):
            frames = [frame_state(self.volume, self.manifest, start + t)[1] for t in (1.5, 1.7, 1.99)]
            self.assertEqual(frames[0]['plane'], frames[-1]['plane'])

    def test_proof_continues_selected_plane_and_holds_two_seconds(self):
        before = frame_state(self.volume, self.manifest, 23.999)[1]
        start = frame_state(self.volume, self.manifest, 24)[1]
        self.assertEqual(before['plane'], start['plane'])
        self.assertEqual(before['face'], start['face'])
        states = [frame_state(self.volume, self.manifest, t)[1] for t in (26, 27, 27.99)]
        self.assertTrue(all(s['face'] == 1 for s in states))
        self.assertEqual(states[0]['plane'], states[-1]['plane'])
        self.assertTrue(all(not any(s['visibility'].values()) for s in states))

    def test_local_and_closing_holds_have_no_geometry_or_zoom_drift(self):
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        for start, end in [(35.5, 36)]:
            a = frame_state(self.volume, self.manifest, start)[1]
            b = frame_state(self.volume, self.manifest, end)[1]
            for key in ('plane', 'zoom', 'face', 'visibility', 'ruler_mm', 'locator',
                        'outro_progress', 'inspection_scale', 'plane_opacity'):
                self.assertEqual(a[key], b[key])
        self.assertEqual(frame_state(self.volume, self.manifest, 30)[1]['zoom'], frame_state(self.volume, self.manifest, 35)[1]['zoom'])

    def test_branch_emphasis_removes_occluding_bone_and_dims_envelope(self):
        state = frame_state(self.volume, self.manifest, 16)[1]
        self.assertEqual(state['visibility']['bones'], 0)
        self.assertLessEqual(state['visibility']['lungs'], 0.04)
        self.assertEqual(state['visibility']['airways'], 1)
        self.assertEqual(state['visibility']['vessels'], 1)
        self.assertEqual(state['branch_emphasis'], 1)
        self.assertFalse(state['show_plane'])

    def test_candidate_crop_state_is_json_serializable_at_wide_and_zoom_holds(self):
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        for t in (28, 28.5, 29, 30, 33, 34, 35, 36):
            state = frame_state(self.volume, self.manifest, t)[1]
            self.assertTrue(json.dumps(state, allow_nan=False))

    def test_opening_stays_on_source_face_side_and_ending_has_no_ribs_or_plane(self):
        self.assertLess(frame_state(self.volume, self.manifest, 2.75)[1]['camera_elevation'], 0)
        self.assertAlmostEqual(frame_state(self.volume, self.manifest, 6.5)[1]['camera_elevation'], 0.35)
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        state = frame_state(self.volume, self.manifest, 34)[1]
        self.assertTrue(state['depth_view'])
        self.assertEqual(state['visibility'], dict(bones=0, lungs=0, airways=0, vessels=0))
        self.assertEqual(state['plane_opacity'], 0)
        self.assertFalse(state['show_plane'])
        self.assertTrue(state['left_ruler_visible'])
        self.assertIsNotNone(state['locator'])

    def test_candidate_view_has_real_depth_without_claiming_image_parity(self):
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        original = self.volume.copy()
        for t in (28, 29, 31, 32.99):
            state = frame_state(self.volume, self.manifest, t)[1]
            self.assertTrue(state['depth_view'])
            self.assertEqual(state['face'], 0)
            self.assertFalse(state['clip'])
            self.assertEqual(state['visibility']['bones'], 0)
            self.assertEqual(state['visibility']['airways'], 0)
            self.assertLess(state['plane_opacity'], 0.2)
            self.assertEqual(state['locator'], self.manifest['annotations'][0])
            self.assertTrue(state['left_ruler_visible'])
        np.testing.assert_array_equal(self.volume, original)
        proof = frame_state(self.volume, self.manifest, 27)[1]
        self.assertEqual(proof['face'], 1)
        self.assertFalse(proof['depth_view'])

    def test_ending_fade_and_camera_tracks_are_continuous_monotone_and_settle(self):
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        a = frame_state(self.volume, self.manifest, 33 - 1e-6)[1]
        b = frame_state(self.volume, self.manifest, 33)[1]
        for key in ('plane', 'inspection_scale', 'plane_opacity', 'visibility'):
            self.assertEqual(a[key], b[key])
        states = [frame_state(self.volume, self.manifest, t)[1] for t in np.linspace(33, 36, 73)]
        progress = [s['outro_progress'] for s in states]
        scales = [s['inspection_scale'] for s in states]
        opacity = [s['plane_opacity'] for s in states]
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(scales, sorted(scales, reverse=True))
        self.assertEqual(opacity, sorted(opacity, reverse=True))
        self.assertAlmostEqual(scales[-1] / scales[0], 1)
        for t in (35.5, 35.9, 36):
            state = frame_state(self.volume, self.manifest, t)[1]
            self.assertEqual(state['outro_progress'], 1)
            self.assertEqual(state['marker_opacity'], 1)
            self.assertEqual(state['visibility']['airways'], 0)
            self.assertIsNotNone(state['locator'])

    def test_right_ct_stays_fixed_through_airway_ending(self):
        self.manifest['annotations'] = [dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)]
        image, reference = frame_state(self.volume, self.manifest, 30)
        for t in (31, 33, 34, 35.9, 36):
            pixels, state = frame_state(self.volume, self.manifest, t)
            np.testing.assert_array_equal(pixels, image)
            self.assertEqual(state['plane'], reference['plane'])
            self.assertEqual(state['ruler_mm'], reference['ruler_mm'])

    def test_n1_persists_through_all_local_frames_and_orbit_has_final_hold(self):
        marker = dict(position_ras=[-2.1, -2.7, 4], radius_mm=1)
        self.manifest['annotations'] = [marker]
        states = [frame_state(self.volume, self.manifest, i / 24)[1] for i in range(672, 864)]
        for state in states:
            self.assertEqual(state['locator'], marker)
            self.assertEqual(state['marker_opacity'], 1)
            self.assertTrue(state['left_ruler_visible'])
            self.assertFalse(any(state['visibility'].values()))
        self.assertEqual(frame_state(self.volume, self.manifest, 30)[1]['outro_progress'], 0)
        self.assertTrue(all(s['outro_progress'] == 1 for s in states[-12:]))
        progress = [s['outro_progress'] for s in states]
        self.assertEqual(progress, sorted(progress))
