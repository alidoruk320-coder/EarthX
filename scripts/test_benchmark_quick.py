import unittest

from scripts.benchmark_quick import frontend_sample_points, point_in_ring


class FrontendSampleMirrorTests(unittest.TestCase):
    def test_returns_at_most_sixteen_interior_points_with_cosine_weights(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [28.0, 40.0], [30.0, 40.0], [30.0, 42.0],
                [28.0, 42.0], [28.0, 40.0],
            ]],
        }
        points = frontend_sample_points(geometry)

        self.assertEqual(len(points), 16)
        self.assertTrue(all(28 < point["lon"] < 30 for point in points))
        self.assertTrue(all(40 < point["lat"] < 42 for point in points))
        self.assertTrue(all(0 < point["weight"] <= 1 for point in points))

    def test_ray_cast_excludes_hole_points(self):
        ring = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
        self.assertTrue(point_in_ring(1, 1, ring))
        self.assertFalse(point_in_ring(3, 1, ring))


if __name__ == "__main__":
    unittest.main()
