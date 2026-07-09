import unittest

import numpy as np

from stl_print_prep.cli import PRESETS, radius_voxels, remove_small_islands


class CliTests(unittest.TestCase):
    def test_presets(self):
        self.assertEqual(set(PRESETS), {"resin", "fdm"})
        self.assertEqual(PRESETS["resin"].close_mm, 1.6)
        self.assertEqual(PRESETS["resin"].dilate_mm, 0.4)
        self.assertEqual(PRESETS["resin"].target_faces, 600_000)
        self.assertEqual(PRESETS["fdm"].close_mm, 2.4)
        self.assertEqual(PRESETS["fdm"].dilate_mm, 1.2)
        self.assertEqual(PRESETS["fdm"].target_faces, 600_000)

    def test_radius_voxels(self):
        self.assertEqual(radius_voxels(0.8, 0.4), 2)
        self.assertEqual(radius_voxels(0.0, 0.4), 0)

    def test_remove_small_islands_keeps_multiple_large_components(self):
        mask = np.zeros((8, 8, 8), dtype=bool)
        mask[0:3, 0:3, 0:3] = True
        mask[5:8, 5:8, 5:8] = True
        mask[4, 0, 0] = True

        cleaned = remove_small_islands(mask, voxel_mm=1.0, min_island_mm3=2.0)

        self.assertTrue(cleaned[1, 1, 1])
        self.assertTrue(cleaned[6, 6, 6])
        self.assertFalse(cleaned[4, 0, 0])


if __name__ == "__main__":
    unittest.main()
