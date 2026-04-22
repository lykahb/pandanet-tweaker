from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_tweaker.models import AssetRole
from pandanet_tweaker.pipeline import inspect_theme


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

    def test_detects_light_and_dark_named_stones(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "light-dark-theme"}', encoding="utf-8")
            (root / "theme.css").write_text(
                """
                .board { background-image: url("board.png"); }
                .dark { background-image: url("stone_dark.png"); }
                .light { background-image: url("stone_light.png"); }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(b"board")
            (root / "stone_dark.png").write_bytes(b"dark")
            (root / "stone_light.png").write_bytes(b"light")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).filename, "stone_dark.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).filename, "stone_light.png")

    def test_prefers_board_named_asset_over_generic_background_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "board-priority-theme"}', encoding="utf-8")
            (root / "theme.css").write_text(
                """
                .board { background-image: url("Board.png"); }
                .background { background-image: url("Background.png"); }
                .black { background-image: url("black.png"); }
                .white { background-image: url("white.png"); }
                """,
                encoding="utf-8",
            )
            (root / "Board.png").write_bytes(b"board")
            (root / "Background.png").write_bytes(b"background")
            (root / "black.png").write_bytes(b"black")
            (root / "white.png").write_bytes(b"white")

            theme = inspect_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.BOARD).filename, "Board.png")

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
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].width, "116.84%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].left, "-10.92%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].height, "184%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].top, "-2%")

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
        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_BLACK]],
            ["glass_black3.png"],
        )
        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_WHITE]],
            ["glass_white.png"],
        )

    def test_collects_multiple_random_variants_per_stone_color(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "baduktv-like"}', encoding="utf-8")
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
                .shudan-stone-image.shudan-sign_1.shudan-random_2 { background-image: url("glass_black4.png"); }
                .shudan-stone-image.shudan-sign_-1 {
                    width: 127%;
                    height: 127%;
                    top: -14%;
                    left: -16%;
                    background-image: url("glass_white3.png");
                }
                .shudan-stone-image.shudan-sign_-1.shudan-random_1 { background-image: url("glass_white2.png"); }
                .shudan-stone-image.shudan-sign_-1.shudan-random_2 { background-image: url("glass_white.png"); }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(b"board")
            (root / "glass_black2.png").write_bytes(b"primary-black")
            (root / "glass_black3.png").write_bytes(b"variant-black-1")
            (root / "glass_black4.png").write_bytes(b"variant-black-2")
            (root / "glass_white3.png").write_bytes(b"primary-white")
            (root / "glass_white2.png").write_bytes(b"variant-white-1")
            (root / "glass_white.png").write_bytes(b"variant-white-2")

            theme = inspect_theme(root)

        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_BLACK]],
            ["glass_black3.png", "glass_black4.png"],
        )
        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_WHITE]],
            ["glass_white2.png", "glass_white.png"],
        )

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
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].width, "119.6%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].width, "116.84%")

    def test_defaults_stone_transforms_to_shudan_inset_when_theme_has_no_css(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "no-css"}', encoding="utf-8")
            (root / "board.png").write_bytes(b"board")
            (root / "black.png").write_bytes(b"black")
            (root / "white.png").write_bytes(b"white")

            theme = inspect_theme(root)

        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].width, "92%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_BLACK].left, "4%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].height, "92%")
        self.assertEqual(theme.stone_transforms[AssetRole.STONE_WHITE].top, "4%")


if __name__ == "__main__":
    unittest.main()
