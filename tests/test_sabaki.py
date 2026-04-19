from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_theme_replacer.models import AssetRole
from pandanet_theme_replacer.pipeline import inspect_theme


class SabakiImportTests(unittest.TestCase):
    def test_detects_board_and_stones_from_directory_theme(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text(
                '{"name": "example-theme", "version": "1.2.3"}',
                encoding="utf-8",
            )
            (root / "theme.css").write_text(
                """
                .board { background-image: url("board.jpg"); }
                .black { background-image: url("black.png"); }
                .white { background-image: url("white.png"); }
                """,
                encoding="utf-8",
            )
            (root / "board.jpg").write_bytes(b"board")
            (root / "black.png").write_bytes(b"black")
            (root / "white.png").write_bytes(b"white")

            theme = inspect_theme(root)

        self.assertEqual(theme.name, "example-theme")
        self.assertEqual({asset.role.value for asset in theme.assets}, {"board", "stone-black", "stone-white"})
        self.assertEqual(theme.warnings, ())

    def test_detects_svg_assets_from_css_references(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "svg-theme"}', encoding="utf-8")
            (root / "theme.css").write_text(
                """
                .board { background-image: url("board.svg"); }
                .black { background-image: url("black.svg?v=1"); }
                .white { background-image: url("white.svg#main"); }
                """,
                encoding="utf-8",
            )
            (root / "board.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
            (root / "black.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
            (root / "white.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

            theme = inspect_theme(root)

        self.assertEqual(theme.name, "svg-theme")
        self.assertEqual({asset.role.value for asset in theme.assets}, {"board", "stone-black", "stone-white"})
        self.assertEqual({asset.filename for asset in theme.assets}, {"board.svg", "black.svg", "white.svg"})

    def test_extracts_stone_transforms_and_role_specific_assets_from_css(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "scaled-stones"}', encoding="utf-8")
            (root / "styles.css").write_text(
                """
                .board { background-image: url("board.svg"); }
                .shudan-stone-image.shudan-sign_1 {
                    width: 127%;
                    height: 127%;
                    top: -14%;
                    left: -16%;
                    background-image: url("glass.png");
                }
                .shudan-stone-image.shudan-sign_-1 {
                    width: 200%;
                    height: 200%;
                    top: -10%;
                    left: -10%;
                    background-image: url("snow.png");
                }
                """,
                encoding="utf-8",
            )
            (root / "board.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
            (root / "glass.png").write_bytes(b"black")
            (root / "snow.png").write_bytes(b"white")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).filename, "glass.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).filename, "snow.png")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].width, "127%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].left, "-16%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].height, "200%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].top, "-10%")

    def test_prefers_css_role_match_for_primary_stone_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "priority-theme"}', encoding="utf-8")
            (root / "styles.css").write_text(
                """
                .board { background-image: url("board.png"); }
                .shudan-stone-image.shudan-sign_1 {
                    width: 130%;
                    height: 127%;
                    top: -14%;
                    left: -14%;
                    background-image: url("glass_black2.png");
                }
                .shudan-stone-image.shudan-sign_-1 {
                    width: 127%;
                    height: 127%;
                    top: -14%;
                    left: -16%;
                    background-image: url("glass_white3.png");
                }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(b"board")
            (root / "glass_black.png").write_bytes(b"unused")
            (root / "glass_black2.png").write_bytes(b"selected")
            (root / "glass_white.png").write_bytes(b"unused")
            (root / "glass_white3.png").write_bytes(b"selected")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).filename, "glass_black2.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).filename, "glass_white3.png")

    def test_ignores_random_variant_rules_when_selecting_primary_stones(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "randomized-theme"}', encoding="utf-8")
            (root / "styles.css").write_text(
                """
                .board { background-image: url("board.png"); }
                .shudan-stone-image.shudan-sign_1 {
                    width: 130%;
                    height: 127%;
                    top: -14%;
                    left: -14%;
                    background-image: url("glass_black2.png");
                }
                .shudan-stone-image.shudan-sign_1.shudan-random_1 { background-image: url("glass_black3.png"); }
                .shudan-stone-image.shudan-sign_-1 {
                    width: 127%;
                    height: 127%;
                    top: -14%;
                    left: -16%;
                    background-image: url("glass_white3.png");
                }
                .shudan-stone-image.shudan-sign_-1.shudan-random_1 { background-image: url("glass_white.png"); }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(b"board")
            (root / "glass_black2.png").write_bytes(b"selected")
            (root / "glass_black3.png").write_bytes(b"random")
            (root / "glass_white3.png").write_bytes(b"selected")
            (root / "glass_white.png").write_bytes(b"random")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).filename, "glass_black2.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).filename, "glass_white3.png")

    def test_strips_comments_before_matching_primary_stone_selectors(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "commented-theme"}', encoding="utf-8")
            (root / "styles.css").write_text(
                """
                .board { background-image: url("board.png"); }
                /* black */
                .shudan-stone-image.shudan-sign_1 {
                    width: 130%;
                    height: 127%;
                    top: -14%;
                    left: -14%;
                    background-image: url("glass_black2.png");
                }
                /* white */
                .shudan-stone-image.shudan-sign_-1 {
                    width: 127%;
                    height: 127%;
                    top: -14%;
                    left: -16%;
                    background-image: url("glass_white3.png");
                }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(b"board")
            (root / "glass_black2.png").write_bytes(b"selected")
            (root / "glass_white3.png").write_bytes(b"selected")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).filename, "glass_black2.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).filename, "glass_white3.png")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].width, "130%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].width, "127%")


if __name__ == "__main__":
    unittest.main()
