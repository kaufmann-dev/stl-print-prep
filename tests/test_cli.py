import argparse
import unittest

from skullmesh_prep.cli import PRESETS, parse_roi, radius_voxels


class FakeImage:
    def GetSpacing(self):
        return (0.4, 0.4, 0.4)

    def GetDimension(self):
        return 3


class CliTests(unittest.TestCase):
    def test_presets_include_decisions(self):
        self.assertEqual(PRESETS["clean"].target_faces, 600_000)
        self.assertEqual(PRESETS["resin-0p8"].close_mm, 0.8)
        self.assertEqual(PRESETS["resin-1p6"].close_mm, 1.6)
        self.assertEqual(PRESETS["manual-orbit-maxilla"].manual_close_mm, 4.8)

    def test_parse_roi(self):
        self.assertEqual(parse_roi("-1,2,-3,4,-5,6"), (-1.0, 2.0, -3.0, 4.0, -5.0, 6.0))

    def test_parse_roi_rejects_wrong_count(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_roi("1,2,3")

    def test_radius_voxels(self):
        self.assertEqual(radius_voxels(0.8, FakeImage()), [2, 2, 2])
        self.assertEqual(radius_voxels(0.0, FakeImage()), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
