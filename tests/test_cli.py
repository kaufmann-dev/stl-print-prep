import unittest

from skullmesh_prep.cli import PRESETS, radius_voxels


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


if __name__ == "__main__":
    unittest.main()
