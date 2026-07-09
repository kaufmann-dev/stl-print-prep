import unittest

from skullmesh_prep.cli import PRESETS, radius_voxels


class FakeImage:
    def GetSpacing(self):
        return (0.4, 0.4, 0.4)

    def GetDimension(self):
        return 3


class CliTests(unittest.TestCase):
    def test_single_resin_preset(self):
        self.assertEqual(set(PRESETS), {"resin"})
        self.assertEqual(PRESETS["resin"].close_mm, 1.6)
        self.assertEqual(PRESETS["resin"].dilate_mm, 0.4)
        self.assertEqual(PRESETS["resin"].target_faces, 600_000)

    def test_radius_voxels(self):
        self.assertEqual(radius_voxels(0.8, FakeImage()), [2, 2, 2])
        self.assertEqual(radius_voxels(0.0, FakeImage()), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
