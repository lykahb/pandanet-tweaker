from __future__ import annotations

import unittest

from pandanet_theme_replacer.targets.pandanet import grid_rgba_to_css_filter


class GridFilterTests(unittest.TestCase):
    def test_grid_rgba_to_css_filter_supports_rgb_and_alpha_hex(self) -> None:
        rgba = grid_rgba_to_css_filter("#336699cc")

        self.assertEqual(rgba.target_rgba, (0x33, 0x66, 0x99, 0xCC))
        self.assertEqual(rgba.opacity_css, "0.8")
        self.assertIn("invert(", rgba.filter_css)
        self.assertIn("sepia(", rgba.filter_css)
        self.assertIn("saturate(", rgba.filter_css)
        self.assertIn("hue-rotate(", rgba.filter_css)
        self.assertIn("brightness(", rgba.filter_css)
        self.assertIn("contrast(", rgba.filter_css)
        self.assertLess(sum(abs(a - b) for a, b in zip(rgba.predicted_rgb, rgba.target_rgba[:3])), 30)

    def test_grid_rgba_to_css_filter_accepts_short_hex(self) -> None:
        rgba = grid_rgba_to_css_filter("#abc8")

        self.assertEqual(rgba.target_rgba, (0xAA, 0xBB, 0xCC, 0x88))

    def test_grid_rgba_to_css_filter_rejects_invalid_hex(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected a hex color"):
            grid_rgba_to_css_filter("#12")


if __name__ == "__main__":
    unittest.main()
