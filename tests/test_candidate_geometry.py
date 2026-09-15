import unittest

import numpy as np
from scipy import ndimage

from ct_education.candidate_geometry import extract_candidate
from ct_education.cinematic import candidate_caption


class CandidateGeometryTests(unittest.TestCase):
    def setUp(self):
        k, j, i = np.indices((41, 41, 41))
        self.volume = np.where((i - 20)**2 + (j - 20)**2 + (k - 20)**2 <= 5**2, 100, -950).astype('float32')
        self.affine = np.diag([-0.5, -0.5, 0.75, 1.0])
        self.affine[:3, 3] = [20, 30, -40]
        self.position = (self.affine @ [20, 20, 20, 1])[:3]

    def test_supported_component_mesh_comes_from_hu_and_preserves_native_array(self):
        original = self.volume.copy()
        result = extract_candidate(self.volume, self.affine, self.position)
        self.assertEqual(result['report']['status'], 'approximate_surface')
        self.assertIsNotNone(result['mesh'])
        vertices = np.array(result['mesh']['positions']).reshape(-1, 3)
        self.assertTrue(np.isfinite(vertices).all())
        self.assertLess(np.linalg.norm(vertices.mean(axis=0) - self.position), 0.5)
        self.assertGreater(len(vertices), 10)
        np.testing.assert_array_equal(original, self.volume)

    def test_air_seed_does_not_create_locator_sphere_as_surface(self):
        result = extract_candidate(np.full_like(self.volume, -950), self.affine, self.position)
        self.assertIsNone(result['mesh'])
        self.assertIsNone(result['density_mesh'])
        self.assertIn('insufficient_seed_connected_evidence', result['report']['reasons'])

    def test_body_or_edge_connection_fails_closed(self):
        result = extract_candidate(np.full_like(self.volume, 50), self.affine, self.position)
        self.assertIsNone(result['mesh'])
        self.assertIsNone(result['density_mesh'])
        self.assertIn('selected_component_reaches_roi_edge', result['report']['reasons'])

    def test_lower_threshold_vessel_connection_is_not_hidden_by_a_fabricated_cut(self):
        self.volume[20, 20, :] = -550
        self.volume[20, 20, 17:24] = 100
        result = extract_candidate(self.volume, self.affine, self.position)
        self.assertIsNone(result['mesh'])
        self.assertIn('lower_threshold_connects_to_roi_edge', result['report']['reasons'])
        self.assertEqual(result['report']['status'], 'localized_region_boundary_unverified')
        self.assertIsNotNone(result['density_mesh'])
        self.assertEqual(result['density_display']['representation_type'], 'exploratory_isodensity')
        self.assertFalse(result['density_display']['verified_nodule_boundary'])
        self.assertIn('lower_threshold_connects_to_roi_edge', result['density_display']['boundary_warnings'])

    def test_strong_threshold_sensitivity_remains_unverified(self):
        k, j, i = np.indices(self.volume.shape)
        radius_squared = (i - 20)**2 + (j - 20)**2 + (k - 20)**2
        density = np.where(radius_squared <= 4, 100, np.where(radius_squared <= 16, -450,
                           np.where(radius_squared <= 49, -550, -950)))
        result = extract_candidate(density.astype('float32'), self.affine, self.position)
        self.assertIsNone(result['mesh'])
        self.assertIn('threshold_sensitive_boundary', result['report']['reasons'])
        self.assertIsNotNone(result['density_mesh'])
        self.assertEqual(result['report']['status'], 'localized_region_boundary_unverified')
        self.assertFalse(result['density_display']['verified_nodule_boundary'])

    def test_outside_seed_and_nonfinite_options_rejected(self):
        with self.assertRaises(ValueError):
            extract_candidate(self.volume, self.affine, [999, 999, 999])
        with self.assertRaises(ValueError):
            extract_candidate(self.volume, self.affine, [np.nan, 0, 0])

    def test_disconnected_density_is_not_merged_into_candidate(self):
        self.volume[4:7, 4:7, 4:7] = 200
        result = extract_candidate(self.volume, self.affine, self.position)
        self.assertIsNotNone(result['mesh'])
        self.assertLess(result['mask'].sum(), 1000)

    def test_exploratory_vertices_follow_native_hu_isovalue_not_a_sphere_prior(self):
        result = extract_candidate(self.volume, self.affine, self.position, threshold_hu=-450,
                                   thresholds=(-600, -450, -300))
        vertices = np.array(result['density_mesh']['positions']).reshape(-1, 3)
        ijk = (np.linalg.inv(self.affine) @ np.c_[vertices, np.ones(len(vertices))].T)[:3].T
        values = ndimage.map_coordinates(self.volume, ijk[:, ::-1].T, order=1)
        np.testing.assert_allclose(values, -450, atol=0.01)
        self.assertEqual(result['density_display']['threshold_hu'], -450)

    def test_density_caption_uses_runtime_threshold_and_never_promotes_boundary(self):
        geometry = dict(density_mesh='candidate/density_surface.json', mesh=None,
                        density_display=dict(threshold_hu=-425), status='localized_region_boundary_unverified')
        self.assertEqual(candidate_caption(geometry), 'CT density surface at -425 HU; not a verified nodule boundary.')
        self.assertIn('boundary unverified', candidate_caption(dict(density_mesh=None)))
