from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_theme_replacer.models import AssetRole, BackgroundMode
from pandanet_theme_replacer.pipeline import (
    build_replacement_plan,
    build_asset_reference_map,
    load_input_theme,
    patch_background_mode,
    patch_css_asset_references,
    patch_grid_color_override,
    patch_css_stone_transforms,
    patch_js_asset_references,
    patch_js_stone_transforms,
    replace_theme,
)
from pandanet_theme_replacer.targets import pandanet
from pandanet_theme_replacer.targets.pandanet import grid_rgba_to_css_filter

PNG_1X1 = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+cG1EAAAAASUVORK5CYII="
)
JPEG_1X1 = b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFhUVFRUVFRUVFRUVFRUVFRUWFhUVFRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGy0lICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAVEAEBAAAAAAAAAAAAAAAAAAABAP/aAAgBAQABBQL/xAAVEQEBAAAAAAAAAAAAAAAAAAAAAf/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwB//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQABPyB//9k="
)


class ReplacementPlanTests(unittest.TestCase):
    def test_resolve_source_asar_prefers_original_archive(self) -> None:
        original_default = pandanet.DEFAULT_ORIGINAL_ASAR_PATH
        app_default = pandanet.DEFAULT_ASAR_PATH
        try:
            with TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                original = root / "original-app.asar"
                app = root / "app.asar"
                original.write_bytes(b"original")
                app.write_bytes(b"patched")
                pandanet.DEFAULT_ORIGINAL_ASAR_PATH = original
                pandanet.DEFAULT_ASAR_PATH = app

                self.assertEqual(pandanet.resolve_source_asar_path(), original)
                self.assertEqual(pandanet.resolve_source_asar_path(app), app)
        finally:
            pandanet.DEFAULT_ORIGINAL_ASAR_PATH = original_default
            pandanet.DEFAULT_ASAR_PATH = app_default

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
        self.assertEqual(
            plan.post_actions,
            (
                "Patch app/css/site.css to set board background mode to 'scale'.",
                "Patch app/css/site.css and app/js/gopanda.js to point at custom board and stone assets.",
            ),
        )
        self.assertEqual(str(plan.operations[0].target_relative_path), "app/img/custom/board.jpg")

    def test_replace_dry_run_reports_grid_override_post_action(self) -> None:
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
                grid_rgba="#336699cc",
                dry_run=True,
            )

        self.assertIn(
            "Patch app/css/site.css to tint .goban > .grid-canvas with #336699cc.",
            plan.post_actions,
        )

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
        self.assertEqual(black_asset.filename, "stone-black.png")

    def test_load_input_theme_preserves_css_selected_stone_variant(self) -> None:
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
            (root / "board.png").write_bytes(JPEG_1X1)
            (root / "glass_black.png").write_bytes(PNG_1X1)
            (root / "glass_black2.png").write_bytes(PNG_1X1)
            (root / "glass_white.png").write_bytes(PNG_1X1)
            (root / "glass_white3.png").write_bytes(PNG_1X1)

            theme = load_input_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_BLACK).source_ref, "glass_black2.png")
        self.assertEqual(theme.first_asset_for_role(AssetRole.STONE_WHITE).source_ref, "glass_white3.png")

    def test_load_input_theme_prefers_board_named_asset_over_background_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "board-priority-theme"}', encoding="utf-8")
            (root / "theme.css").write_text(
                """
                .board { background-image: url("images/Board.png"); }
                .background { background-image: url("images/Background.png"); }
                .black { background-image: url("black.png"); }
                .white { background-image: url("white.png"); }
                """,
                encoding="utf-8",
            )
            images = root / "images"
            images.mkdir()
            (images / "Board.png").write_bytes(PNG_1X1)
            (images / "Background.png").write_bytes(PNG_1X1)
            (root / "black.png").write_bytes(PNG_1X1)
            (root / "white.png").write_bytes(PNG_1X1)

            theme = load_input_theme(root)

        self.assertEqual(theme.first_asset_for_role(AssetRole.BOARD).source_ref, "images/Board.png")

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

            patch_background_mode(css_path, BackgroundMode.SCALE, "../img/custom/board.svg")
            css_text = css_path.read_text(encoding="utf-8")
            self.assertIn('background: url("../img/custom/board.svg") no-repeat;', css_text)
            self.assertIn("background-size: 100% 100%;", css_text)
            self.assertIn("background-position: center;", css_text)

            patch_background_mode(css_path, BackgroundMode.REPEAT, "../img/custom/board.svg")
            css_text = css_path.read_text(encoding="utf-8")
            self.assertIn('background: url("../img/custom/board.svg") repeat;', css_text)
            self.assertNotIn("background-size: 100% 100%;", css_text)

    def test_css_and_js_refs_are_patched_to_custom_assets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "svg-theme"}', encoding="utf-8")
            (root / "theme.css").write_text(
                """
                .board { background-image: url("board.svg"); }
                .black { background-image: url("black.svg"); }
                .white { background-image: url("white.svg"); }
                """,
                encoding="utf-8",
            )
            svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
            (root / "board.svg").write_text(svg, encoding="utf-8")
            (root / "black.svg").write_text(svg, encoding="utf-8")
            (root / "white.svg").write_text(svg, encoding="utf-8")
            theme = load_input_theme(root)

            css_path = root / "site.css"
            css_path.write_text(
                """
                .goban { background: url("../img/wood-board.jpg") repeat; }
                .capture.white { background: url("../img/50/stone-black-w-shadow.png") no-repeat; }
                .capture.black { background: url("../img/50/stone-white-w-shadow.png") no-repeat; }
                .mark.white { background-image: url("../img/50/stone-white.png"); }
                .mark.black { background-image: url("../img/50/stone-black.png"); }
                """.strip()
                + "\n",
                encoding="utf-8",
            )
            js_path = root / "gopanda.js"
            js_path.write_text(
                'function Qwa(){e0.src="img/50/stone-black.png";f0.src="img/50/stone-white.png";}',
                encoding="utf-8",
            )

            refs = build_asset_reference_map(theme)
            patch_css_asset_references(css_path, refs)
            patch_js_asset_references(js_path, refs)

            css_text = css_path.read_text(encoding="utf-8")
            js_text = js_path.read_text(encoding="utf-8")

        self.assertIn("../img/custom/board.svg", css_text)
        self.assertIn("../img/custom/stone-black.svg", css_text)
        self.assertIn("../img/custom/stone-white.svg", css_text)
        self.assertIn('img/custom/stone-black.svg', js_text)
        self.assertIn('img/custom/stone-white.svg', js_text)

    def test_transformed_stones_patch_direct_refs_and_rendering_offsets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "wrapped-stones"}', encoding="utf-8")
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
            (root / "glass.png").write_bytes(PNG_1X1)
            (root / "snow.png").write_bytes(PNG_1X1)

            theme = load_input_theme(root)
            refs = build_asset_reference_map(theme)
            css_path = root / "site.css"
            css_path.write_text(
                """
                .goban-page .lid .lid-captures .capture.white {
                  background: url("../img/50/stone-black-w-shadow.png") no-repeat;
                  background-size: 100%;
                }
                .goban-page .lid .lid-captures .capture.black {
                  background: url("../img/50/stone-white-w-shadow.png") no-repeat;
                  background-size: 100%;
                }
                .goban-page .info-panel .info-panel-wrapper .name-rank .mark.white {
                  background-image: url("../img/50/stone-white.png");
                }
                .goban-page .info-panel .info-panel-wrapper .name-rank .mark.black {
                  background-image: url("../img/50/stone-black.png");
                }
                """.strip()
                + "\n",
                encoding="utf-8",
            )
            js_path = root / "gopanda.js"
            js_path.write_text(
                'function r0(a,b,c){var d=J(a);a=t(d,Uy);var e=t(d,rH);d=t(d,jx);var f=G(c,0,null);c=G(c,1,null);var g=new l(null,2,[SC,e0,WG,f0],null);b=b.j?b.j(g):b.call(null,g);a.drawImage(b,f*e,(d-c-1)*e,e,e)}',
                encoding="utf-8",
            )

            patch_css_asset_references(css_path, refs)
            patch_js_asset_references(js_path, refs)
            patch_css_stone_transforms(css_path, theme.stone_transforms)
            patch_js_stone_transforms(js_path, theme.stone_transforms)
            css_text = css_path.read_text(encoding="utf-8")
            js_text = js_path.read_text(encoding="utf-8")

        css_refs = refs[1]
        js_refs = refs[2]
        self.assertEqual(css_refs[AssetRole.STONE_BLACK], "../img/custom/stone-black.png")
        self.assertEqual(css_refs[AssetRole.STONE_WHITE], "../img/custom/stone-white.png")
        self.assertEqual(js_refs[AssetRole.STONE_BLACK], "img/custom/stone-black.png")
        self.assertEqual(js_refs[AssetRole.STONE_WHITE], "img/custom/stone-white.png")
        self.assertIn("background-size: 127% 127%;", css_text)
        self.assertIn("background-position: -16% -14%;", css_text)
        self.assertIn("background-size: 200% 200%;", css_text)
        self.assertIn("background-position: -10% -10%;", css_text)
        self.assertIn('b===e0?{left:-16,top:-14,width:127,height:127}', js_text)
        self.assertIn('b===f0?{left:-10,top:-10,width:200,height:200}', js_text)
        self.assertIn('a.drawImage(b,k+h.left*e/100,n+h.top*e/100,h.width*e/100,h.height*e/100)', js_text)

    def test_patch_grid_color_override_appends_goban_scoped_rule(self) -> None:
        with TemporaryDirectory() as temp_dir:
            css_path = Path(temp_dir) / "site.css"
            css_path.write_text(".goban-page .goban canvas.grid-canvas {\n  z-index: 1;\n}\n", encoding="utf-8")

            patch_grid_color_override(css_path, grid_rgba_to_css_filter("#336699cc"))
            css_text = css_path.read_text(encoding="utf-8")

        self.assertIn("/* pandanet-theme-replacer grid override */", css_text)
        self.assertIn(".goban > .grid-canvas {", css_text)
        self.assertIn("filter: ", css_text)
        self.assertIn("opacity: 0.8;", css_text)


if __name__ == "__main__":
    unittest.main()
