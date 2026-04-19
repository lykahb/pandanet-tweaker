from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_theme_replacer.models import AssetRole, BackgroundMode
from pandanet_theme_replacer.pipeline import load_input_theme, patch_background_mode, replace_theme

PNG_1X1 = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+cG1EAAAAASUVORK5CYII="
)
JPEG_1X1 = b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFhUVFRUVFRUVFRUVFRUVFRUWFhUVFRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGy0lICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAVEAEBAAAAAAAAAAAAAAAAAAABAP/aAAgBAQABBQL/xAAVEQEBAAAAAAAAAAAAAAAAAAAAAf/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwB//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQABPyB//9k="
)


class ReplacementPlanTests(unittest.TestCase):
    def test_replace_uses_explicit_assets_in_dry_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            plan = replace_theme(
                None,
                root / "app.asar",
                root / "out.asar",
                background_path=board,
                black_stone_path=black,
                white_stone_path=white,
                background_mode=BackgroundMode.SCALE,
                dry_run=True,
            )

        self.assertEqual(len(plan.operations), 3)
        self.assertTrue(all(operation.status == "ready" for operation in plan.operations))
        self.assertEqual(plan.post_actions, ("Patch app/css/site.css to set board background mode to 'scale'.",))

    def test_load_input_theme_merges_explicit_assets_over_theme(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            theme_root = root / "theme"
            theme_root.mkdir()
            (theme_root / "package.json").write_text('{"name": "example-theme"}', encoding="utf-8")
            (theme_root / "theme.css").write_text(
                """
                .board { background-image: url("board.jpg"); }
                .black { background-image: url("black.png"); }
                .white { background-image: url("white.png"); }
                """,
                encoding="utf-8",
            )
            (theme_root / "board.jpg").write_bytes(JPEG_1X1)
            (theme_root / "black.png").write_bytes(PNG_1X1)
            (theme_root / "white.png").write_bytes(PNG_1X1)

            override = root / "override-black.png"
            override.write_bytes(PNG_1X1)

            theme = load_input_theme(
                theme_root,
                black_stone_path=override,
            )

        black_asset = theme.first_asset_for_role(AssetRole.STONE_BLACK)
        self.assertIsNotNone(black_asset)
        assert black_asset is not None
        self.assertEqual(black_asset.source_ref, str(override.resolve()))

    def test_patch_background_mode_updates_goban_css_block(self) -> None:
        with TemporaryDirectory() as temp_dir:
            css_path = Path(temp_dir) / "site.css"
            css_path.write_text(
                """
.goban {
  background: url("../img/wood-board.jpg") repeat;
  position: absolute;
}
""".strip()
                + "\n",
                encoding="utf-8",
            )

            patch_background_mode(css_path, BackgroundMode.SCALE)
            css_text = css_path.read_text(encoding="utf-8")
            self.assertIn('background: url("../img/wood-board.jpg") no-repeat;', css_text)
            self.assertIn("background-size: 100% 100%;", css_text)
            self.assertIn("background-position: center;", css_text)

            patch_background_mode(css_path, BackgroundMode.REPEAT)
            css_text = css_path.read_text(encoding="utf-8")
            self.assertIn('background: url("../img/wood-board.jpg") repeat;', css_text)
            self.assertNotIn("background-size: 100% 100%;", css_text)


if __name__ == "__main__":
    unittest.main()
