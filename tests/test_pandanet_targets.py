from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from pandanet_tweaker.targets.pandanet import (
    default_asar_dir,
    grid_rgba_to_css_filter,
    infer_install_target_asar_path,
    resolve_source_asar_path,
)


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


class PandanetTargetPathTests(unittest.TestCase):
    def test_default_asar_dir_uses_windows_localappdata_when_available(self) -> None:
        with (
            patch("pandanet_tweaker.targets.pandanet.platform.system", return_value="Windows"),
            patch.dict("pandanet_tweaker.targets.pandanet.os.environ", {"LOCALAPPDATA": r"C:\Users\alice\AppData\Local"}, clear=True),
        ):
            self.assertEqual(
                default_asar_dir(),
                Path(r"C:\Users\alice\AppData\Local") / "Programs" / "GoPanda2" / "resources",
            )

    def test_resolve_source_asar_path_prefers_windows_original_archive(self) -> None:
        resources_dir = Path(r"C:\Users\alice\AppData\Local\Programs\GoPanda2\resources")
        original_asar = resources_dir / "original-app.asar"
        app_asar = resources_dir / "app.asar"

        with (
            patch("pandanet_tweaker.targets.pandanet.default_asar_dir", return_value=resources_dir),
            patch.object(Path, "is_file", autospec=True, side_effect=lambda self: self == original_asar),
        ):
            self.assertEqual(resolve_source_asar_path(), original_asar)
            self.assertEqual(resolve_source_asar_path(app_asar), app_asar)

    def test_infer_install_target_asar_path_uses_sibling_app_asar_for_original_archive(self) -> None:
        self.assertEqual(
            infer_install_target_asar_path(Path("C:/Users/alice/AppData/Local/Programs/GoPanda2/resources/original-app.asar")),
            Path("C:/Users/alice/AppData/Local/Programs/GoPanda2/resources/app.asar"),
        )

    def test_infer_install_target_asar_path_returns_none_for_unknown_archive_name(self) -> None:
        self.assertIsNone(infer_install_target_asar_path(Path("original-win-app.asar")))


if __name__ == "__main__":
    unittest.main()
