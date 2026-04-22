from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pandanet_tweaker.errors import ConfigurationError
from pandanet_tweaker.models import (
    AssetRole,
    BackgroundMode,
    ReplaceRequest,
    StoneTransform,
    ThemeInputSpec,
)
from pandanet_tweaker.pipeline import (
    build_replacement_plan,
    build_asset_reference_map,
    build_stone_variant_reference_map,
    build_runtime_stone_transform_script,
    load_input_theme,
    patch_background_mode,
    patch_css_asset_references,
    patch_grid_color_override,
    patch_shadow_canvas_override,
    patch_css_stone_transforms,
    patch_index_html_for_runtime_script,
    patch_js_asset_references,
    patch_js_expand_goban_canvas,
    patch_js_force_full_board_redraw,
    patch_js_translate_expanded_goban_context,
    write_runtime_stone_transform_script,
    replace_theme,
)
from pandanet_tweaker.targets import pandanet
from pandanet_tweaker.targets.pandanet import grid_rgba_to_css_filter

PNG_1X1 = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+cG1EAAAAASUVORK5CYII="
)
JPEG_1X1 = b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBAVFhUVFRUVFRUVFRUVFRUVFRUWFhUVFRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGy0lICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAgMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQID/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB6A//xAAVEAEBAAAAAAAAAAAAAAAAAAABAP/aAAgBAQABBQL/xAAVEQEBAAAAAAAAAAAAAAAAAAAAAf/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwB//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAEP/aAAgBAQABPyB//9k="
)


class ReplacementPlanTests(unittest.TestCase):
    def _make_input_spec(
        self,
        *,
        theme_path: Path | None = None,
        board_background_path: Path | None = None,
        black_stone_path: Path | None = None,
        white_stone_path: Path | None = None,
        theme_format: str = "auto",
    ) -> ThemeInputSpec:
        return ThemeInputSpec(
            theme_path=theme_path,
            theme_format=theme_format,
            board_background_path=board_background_path,
            black_stone_path=black_stone_path,
            white_stone_path=white_stone_path,
        )

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
                ReplaceRequest(
                    input_spec=self._make_input_spec(
                        board_background_path=board,
                        black_stone_path=black,
                        white_stone_path=white,
                    ),
                    asar_path=root / "app.asar",
                    output_path=root / "out.asar",
                    background_mode=BackgroundMode.SCALE,
                    dry_run=True,
                )
            )

        self.assertEqual(len(plan.operations), 3)
        self.assertTrue(all(operation.status == "ready" for operation in plan.operations))
        self.assertEqual(
            plan.post_actions,
            (
                "Patch app/css/site.css to set board background mode to 'scale'.",
                "Patch app/css/site.css and app/js/gopanda.js to point at custom board and stone assets.",
                "Patch app/css/site.css to hide .goban canvas.shadow-canvas.",
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
                ReplaceRequest(
                    input_spec=self._make_input_spec(
                        board_background_path=board,
                        black_stone_path=black,
                        white_stone_path=white,
                    ),
                    asar_path=root / "app.asar",
                    output_path=root / "out.asar",
                    grid_rgba="#336699cc",
                    dry_run=True,
                )
            )

        self.assertIn(
            "Patch app/css/site.css to tint .goban > .grid-canvas with #336699cc.",
            plan.post_actions,
        )

    def test_replace_dry_run_can_leave_default_shadows_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            plan = replace_theme(
                ReplaceRequest(
                    input_spec=self._make_input_spec(
                        board_background_path=board,
                        black_stone_path=black,
                        white_stone_path=white,
                    ),
                    asar_path=root / "app.asar",
                    output_path=root / "out.asar",
                    disable_default_shadows=False,
                    dry_run=True,
                )
            )

        self.assertNotIn(
            "Patch app/css/site.css to hide .goban canvas.shadow-canvas.",
            plan.post_actions,
        )

    def test_replace_stages_only_patched_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            asar = root / "original-app.asar"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)
            asar.write_bytes(b"asar")

            file_map = {
                pandanet.PANDANET_SITE_CSS_PATH: (
                    '.goban {\n  background: url("../img/wood-board.jpg") repeat;\n}\n'
                    '.goban-page .lid .lid-captures .capture.white {\n'
                    '  background: url("../img/50/stone-black-w-shadow.png") no-repeat;\n}\n'
                    '.goban-page .lid .lid-captures .capture.black {\n'
                    '  background: url("../img/50/stone-white-w-shadow.png") no-repeat;\n}\n'
                    '.goban-page .info-panel .info-panel-wrapper .name-rank .mark.white {\n'
                    '  background-image: url("../img/50/stone-white.png");\n}\n'
                    '.goban-page .info-panel .info-panel-wrapper .name-rank .mark.black {\n'
                    '  background-image: url("../img/50/stone-black.png");\n}\n'
                ).encode("utf-8"),
                pandanet.PANDANET_GOPANDA_JS_PATH: (
                    'function Qwa(){e0.src="img/50/stone-black.png";f0.src="img/50/stone-white.png";}'
                ).encode("utf-8"),
            }

            with (
                patch(
                    "pandanet_tweaker.pipeline.read_asar_file",
                    side_effect=lambda _asar, path: file_map[path],
                ) as read_file,
                patch("pandanet_tweaker.pipeline.rebuild_asar") as rebuild,
            ):
                replace_theme(
                    ReplaceRequest(
                        input_spec=self._make_input_spec(
                            board_background_path=board,
                            black_stone_path=black,
                            white_stone_path=white,
                        ),
                        asar_path=asar,
                        output_path=root / "out.asar",
                        background_mode=BackgroundMode.SCALE,
                    )
                )

        self.assertEqual(
            [call.args[1] for call in read_file.call_args_list],
            [pandanet.PANDANET_SITE_CSS_PATH, pandanet.PANDANET_GOPANDA_JS_PATH],
        )
        rebuild.assert_called_once()
        replacements = rebuild.call_args.args[2]
        self.assertIn(Path("app/img/custom/board.jpg"), replacements)
        self.assertIn(Path("app/img/custom/stone-black.png"), replacements)
        self.assertIn(Path("app/img/custom/stone-white.png"), replacements)
        self.assertIn(pandanet.PANDANET_SITE_CSS_PATH, replacements)
        self.assertIn(pandanet.PANDANET_GOPANDA_JS_PATH, replacements)
        self.assertNotIn(pandanet.PANDANET_INDEX_HTML_PATH, replacements)
        self.assertNotIn(pandanet.PANDANET_THEME_RUNTIME_JS_PATH, replacements)
        self.assertIn("../img/custom/board.jpg", replacements[pandanet.PANDANET_SITE_CSS_PATH].decode("utf-8"))
        self.assertIn('img/custom/stone-black.png', replacements[pandanet.PANDANET_GOPANDA_JS_PATH].decode("utf-8"))

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
                self._make_input_spec(
                    theme_path=theme_root,
                    black_stone_path=override,
                )
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

            theme = load_input_theme(self._make_input_spec(theme_path=root))

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

            theme = load_input_theme(self._make_input_spec(theme_path=root))

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

    def test_patch_shadow_canvas_override_hides_shadow_canvas_and_is_reversible(self) -> None:
        with TemporaryDirectory() as temp_dir:
            css_path = Path(temp_dir) / "site.css"
            css_path.write_text(".goban canvas.shadow-canvas {\n  opacity: 1;\n}\n", encoding="utf-8")

            patch_shadow_canvas_override(css_path, disable_default_shadows=True)
            patch_shadow_canvas_override(css_path, disable_default_shadows=True)
            css_text = css_path.read_text(encoding="utf-8")
            self.assertEqual(css_text.count("/* pandanet-tweaker shadow override */"), 1)
            self.assertIn(".goban canvas.shadow-canvas {", css_text)
            self.assertIn("display: none;", css_text)

            patch_shadow_canvas_override(css_path, disable_default_shadows=False)
            reverted_css_text = css_path.read_text(encoding="utf-8")
            self.assertNotIn("/* pandanet-tweaker shadow override */", reverted_css_text)
            self.assertNotIn("display: none;", reverted_css_text)

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
            theme = load_input_theme(self._make_input_spec(theme_path=root))

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

    def test_transformed_stones_patch_direct_refs_and_runtime_hook(self) -> None:
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

            theme = load_input_theme(self._make_input_spec(theme_path=root))
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
                .goban-page .lid .lid-captures .capture {
                  width: 18%;
                  height: 18%;
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
                'function q0(a,b,c,d){var e=function(){var k=W(F(["goban-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),f=function(){var k=W(F(["grid-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),g=function(){var k=W(F(["shadow-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}();return jk([Xr,jx,Qia,yca,QA,R,Qx,voa,Uy,rH],[f.getContext("2d"),c,g,e,g.getContext("2d"),a,d,f,e.getContext("2d"),b])}'
                'function K4(a,b){var c=J(b);b=t(c,lD);c=t(c,Cz);return new Sf(null,J4(a,"grid-canvas",c),new Sf(null,J4(a,"shadow-canvas",b),new Sf(null,J4(a,"goban-canvas",b),null,1,null),2,null),3,null)}'
                'function N4(a,b){OT(function(){var n=W(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null),F(["px"]));}'
                'function r0(a,b,c){var d=J(a);a=t(d,Uy);var e=t(d,rH);d=t(d,jx);var f=G(c,0,null);c=G(c,1,null);var g=new l(null,2,[SC,e0,WG,f0],null);b=b.j?b.j(g):b.call(null,g);a.drawImage(b,f*e,(d-c-1)*e,e,e)}'
                'function V0(a,b){var c=J(a);a=t(c,Rw);c=t(c,lB);w0(a,b);return U0(a,c,b)}'
                'function W0(a){}',
                encoding="utf-8",
            )
            index_html_path = root / "index.html"
            index_html_path.write_text(
                """
                <!DOCTYPE html>
                <html>
                  <body>
                    <script src="js/gopanda.js" type="text/javascript"></script>
                  </body>
                </html>
                """.strip()
                + "\n",
                encoding="utf-8",
            )
            runtime_js_path = root / "pandanet-tweaker.js"

            patch_css_asset_references(css_path, refs)
            patch_js_asset_references(js_path, refs)
            patch_js_expand_goban_canvas(js_path)
            patch_js_translate_expanded_goban_context(js_path)
            patch_js_force_full_board_redraw(js_path)
            patch_css_stone_transforms(css_path, theme.stone_transforms)
            write_runtime_stone_transform_script(runtime_js_path, theme.stone_transforms, refs.js_refs, {}, 0.0)
            patch_index_html_for_runtime_script(index_html_path)
            css_text = css_path.read_text(encoding="utf-8")
            js_text = js_path.read_text(encoding="utf-8")
            runtime_js_text = runtime_js_path.read_text(encoding="utf-8")
            index_html_text = index_html_path.read_text(encoding="utf-8")

        self.assertEqual(refs.css_refs[AssetRole.STONE_BLACK], "../img/custom/stone-black.png")
        self.assertEqual(refs.css_refs[AssetRole.STONE_WHITE], "../img/custom/stone-white.png")
        self.assertEqual(refs.js_refs[AssetRole.STONE_BLACK], "img/custom/stone-black.png")
        self.assertEqual(refs.js_refs[AssetRole.STONE_WHITE], "img/custom/stone-white.png")
        self.assertIn("width: 24%;", css_text)
        self.assertIn("height: 24%;", css_text)
        self.assertIn("margin-left: -3%;", css_text)
        self.assertIn("margin-top: -3%;", css_text)
        self.assertIn("background-size: 87.63% 87.63%;", css_text)
        self.assertIn("background-position: -8.19% -6.69%;", css_text)
        self.assertIn("background-size: 138% 138%;", css_text)
        self.assertIn("background-position: -1.5% -1.5%;", css_text)
        self.assertIn("background-size: 116.84% 116.84%;", css_text)
        self.assertIn("background-position: -10.92% -8.92%;", css_text)
        self.assertIn("background-size: 184% 184%;", css_text)
        self.assertIn("background-position: -2% -2%;", css_text)
        self.assertIn('J4(a,"goban-canvas",c)', js_text)
        self.assertIn('new l(null,2,[Ky,0,Qz,0],null)', js_text)
        self.assertIn('window.__pandanetTweakerInstallGobanContext?window.__pandanetTweakerInstallGobanContext(e.getContext("2d"),d):e.getContext("2d")', js_text)
        self.assertIn("function V0(a,b){return W0(a)}", js_text)
        self.assertIn("CanvasRenderingContext2D.prototype", runtime_js_text)
        self.assertIn('"img/custom/stone-black.png": { left: -10.92, top: -8.92, width: 116.84, height: 116.84, variants: [] }', runtime_js_text)
        self.assertIn('"img/custom/stone-white.png": { left: -2, top: -2, width: 184, height: 184, variants: [] }', runtime_js_text)
        self.assertIn("arguments.length === 5", runtime_js_text)
        self.assertIn("src.indexOf(key) !== -1", runtime_js_text)
        self.assertIn('src="js/pandanet-tweaker.js"', index_html_text)

    def test_patch_js_force_full_board_redraw_replaces_incremental_redraw(self) -> None:
        with TemporaryDirectory() as temp_dir:
            js_path = Path(temp_dir) / "gopanda.js"
            js_path.write_text(
                "function w0(a,b){}function U0(a,b,c){}function V0(a,b){var c=J(a);a=t(c,Rw);c=t(c,lB);w0(a,b);return U0(a,c,b)}function W0(a){}",
                encoding="utf-8",
            )

            patch_js_force_full_board_redraw(js_path)
            patch_js_force_full_board_redraw(js_path)
            js_text = js_path.read_text(encoding="utf-8")

        self.assertIn("function V0(a,b){return W0(a)}", js_text)
        self.assertEqual(js_text.count("function V0(a,b){return W0(a)}"), 1)

    def test_patch_js_expand_goban_canvas_replaces_inset_layout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            js_path = Path(temp_dir) / "gopanda.js"
            js_path.write_text(
                'function K4(a,b){var c=J(b);b=t(c,lD);c=t(c,Cz);return new Sf(null,J4(a,"grid-canvas",c),new Sf(null,J4(a,"shadow-canvas",b),new Sf(null,J4(a,"goban-canvas",b),null,1,null),2,null),3,null)}'
                'function N4(a,b){OT(function(){var n=W(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null),F(["px"]));'
                'OT(function(){var n=W(F(["shadow-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),new l(null,2,[Ky,WC.j(b),Qz,WC.j(b)],null),F(["px"]));}',
                encoding="utf-8",
            )

            patch_js_expand_goban_canvas(js_path)
            patch_js_expand_goban_canvas(js_path)
            js_text = js_path.read_text(encoding="utf-8")

        self.assertIn('J4(a,"goban-canvas",c)', js_text)
        self.assertEqual(js_text.count('J4(a,"goban-canvas",c)'), 1)
        self.assertIn(
            'OT(function(){var n=W(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),new l(null,2,[Ky,0,Qz,0],null),F(["px"]));',
            js_text,
        )

    def test_patch_js_expand_goban_canvas_handles_wrapped_positioning_block(self) -> None:
        with TemporaryDirectory() as temp_dir:
            js_path = Path(temp_dir) / "gopanda.js"
            js_path.write_text(
                'function K4(a,b){var c=J(b);b=t(c,lD);c=t(c,Cz);return new Sf(null,J4(a,"grid-canvas",c),new Sf(null,J4(a,"shadow-canvas",b),new Sf(null,J4(a,"goban-canvas",b),null,1,null),2,null),3,null)}'
                'function N4(a,b){OT(function(){var n=\nW(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null),F(["px"]));}',
                encoding="utf-8",
            )

            patch_js_expand_goban_canvas(js_path)
            js_text = js_path.read_text(encoding="utf-8")

        self.assertIn('J4(a,"goban-canvas",c)', js_text)
        self.assertIn('new l(null,2,[Ky,0,Qz,0],null)', js_text)

    def test_patch_js_translate_expanded_goban_context_wraps_q0_goban_context(self) -> None:
        with TemporaryDirectory() as temp_dir:
            js_path = Path(temp_dir) / "gopanda.js"
            js_path.write_text(
                'function q0(a,b,c,d){var e=function(){var k=W(F(["goban-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),f=function(){var k=W(F(["grid-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),g=function(){var k=W(F(["shadow-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}();return jk([Xr,jx,Qia,yca,QA,R,Qx,voa,Uy,rH],[f.getContext("2d"),c,g,e,g.getContext("2d"),a,d,f,e.getContext("2d"),b])}',
                encoding="utf-8",
            )

            patch_js_translate_expanded_goban_context(js_path)
            patch_js_translate_expanded_goban_context(js_path)
            js_text = js_path.read_text(encoding="utf-8")

        self.assertIn(
            'window.__pandanetTweakerInstallGobanContext?window.__pandanetTweakerInstallGobanContext(e.getContext("2d"),d):e.getContext("2d")',
            js_text,
        )

    def test_patch_index_html_for_runtime_script_is_idempotent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            index_html_path = Path(temp_dir) / "index.html"
            index_html_path.write_text(
                """
                <!DOCTYPE html>
                <html>
                  <body>
                    <script src="js/gopanda.js" type="text/javascript"></script>
                  </body>
                </html>
                """.strip()
                + "\n",
                encoding="utf-8",
            )

            patch_index_html_for_runtime_script(index_html_path)
            patch_index_html_for_runtime_script(index_html_path)
            html_text = index_html_path.read_text(encoding="utf-8")

        self.assertEqual(html_text.count('src="js/pandanet-tweaker.js"'), 1)

    def test_build_runtime_stone_transform_script_uses_js_refs(self) -> None:
        script = build_runtime_stone_transform_script(
            {
                AssetRole.STONE_BLACK: StoneTransform(
                    width="116.84%",
                    height="116.84%",
                    top="-8.92%",
                    left="-10.92%",
                ),
            },
            {
                AssetRole.STONE_BLACK: "img/custom/stone-black.svg",
            },
            {},
            0.0,
        )

        self.assertIn('"img/custom/stone-black.svg": { left: -10.92, top: -8.92, width: 116.84, height: 116.84, variants: [] }', script)
        self.assertIn("proto.__pandanetTweakerDrawImagePatched = true;", script)

    def test_build_runtime_stone_transform_script_uses_scaled_transforms(self) -> None:
        script = build_runtime_stone_transform_script(
            {
                AssetRole.STONE_BLACK: StoneTransform(
                    width="120%",
                    height="120%",
                    top="-10%",
                    left="-10%",
                ),
            },
            {
                AssetRole.STONE_BLACK: "img/custom/stone-black.png",
            },
            {},
            0.0,
        )

        self.assertIn('"img/custom/stone-black.png": { left: -10, top: -10, width: 120, height: 120, variants: [] }', script)

    def test_build_runtime_stone_transform_script_includes_random_variants(self) -> None:
        script = build_runtime_stone_transform_script(
            {
                AssetRole.STONE_BLACK: StoneTransform(
                    width="116.84%",
                    height="116.84%",
                    top="-8.92%",
                    left="-10.92%",
                ),
            },
            {
                AssetRole.STONE_BLACK: "img/custom/stone-black.png",
            },
            {
                AssetRole.STONE_BLACK: (
                    "img/custom/stone-black-variant-1.png",
                    "img/custom/stone-black-variant-2.png",
                ),
            },
            0.0,
        )

        self.assertIn(
            '"img/custom/stone-black.png": { left: -10.92, top: -8.92, width: 116.84, height: 116.84, variants: ["img/custom/stone-black-variant-1.png", "img/custom/stone-black-variant-2.png"] }',
            script,
        )
        self.assertIn("var variantImages = {};", script)
        self.assertIn("var chosenVariantIndexes = {};", script)
        self.assertIn("Math.floor(Math.random() * config.variants.length)", script)

    def test_build_runtime_stone_transform_script_includes_fuzzy_placement(self) -> None:
        script = build_runtime_stone_transform_script(
            {},
            {
                AssetRole.STONE_BLACK: "img/custom/stone-black.png",
                AssetRole.STONE_WHITE: "img/custom/stone-white.png",
            },
            {},
            0.25,
        )

        self.assertIn("var fuzzyStonePlacement = 0.25;", script)
        self.assertIn("var chosenShifts = {};", script)
        self.assertIn("function removeConflictingNeighborShifts(shiftMap, boardKey, cellX, cellY)", script)
        self.assertIn("chosenShifts[key] = randomInt(8);", script)
        self.assertIn("var diagonalScale = Math.SQRT1_2 || (1 / Math.sqrt(2));", script)
        self.assertIn("drawWidth * fuzzyStonePlacement", script)
        self.assertIn("window.__pandanetTweakerInstallGobanContext = function(ctx, inset)", script)
        self.assertIn("function isGobanCanvas(ctx)", script)
        self.assertIn("function getInstalledGobanInset(ctx)", script)
        self.assertIn("function isLikelyFullCanvasClear(ctx, x, y, w, h)", script)
        self.assertIn("var originalClearRect = proto.clearRect;", script)
        self.assertIn("var originalArc = proto.arc;", script)
        self.assertIn("var finalDx = dx + (dw * config.left / 100) + fuzzyOffset.x;", script)
        self.assertIn("var finalDy = dy + (dh * config.top / 100) + fuzzyOffset.y;", script)
        self.assertIn("setPendingMarkerState(this, dx + dw / 2, dy + dh / 2, finalDx + drawWidth / 2, finalDy + drawHeight / 2, Math.min(dw, dh));", script)
        self.assertIn("proto.clearRect = function(x, y, w, h)", script)
        self.assertIn("if (isLikelyFullCanvasClear(this, x, y, w, h)) {", script)
        self.assertIn("if (typeof this.setTransform === 'function') this.setTransform(1, 0, 0, 1, 0, 0);", script)
        self.assertIn("var result = originalClearRect.call(this, 0, 0, canvas.width, canvas.height);", script)
        self.assertIn("return originalClearRect.call(this, x, y, w, h);", script)
        self.assertIn("proto.arc = function(x, y, r, startAngle, endAngle, counterclockwise)", script)
        self.assertIn("if (isLikelyMarkerArc(this, state, x, y, r)) {", script)

    def test_replace_dry_run_reports_fuzzy_stone_placement_post_actions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            plan = replace_theme(
                ReplaceRequest(
                    input_spec=self._make_input_spec(
                        board_background_path=board,
                        black_stone_path=black,
                        white_stone_path=white,
                    ),
                    asar_path=root / "app.asar",
                    output_path=root / "out.asar",
                    fuzzy_stone_placement=0.25,
                    dry_run=True,
                )
            )

        self.assertIn(
            "Inject app/js/pandanet-tweaker.js and patch app/index.html to apply stone rendering overrides at runtime.",
            plan.post_actions,
        )
        self.assertIn(
            "Apply Shudan-style fuzzy stone placement with maximum offset 0.25 stone diameters.",
            plan.post_actions,
        )

    def test_replace_dry_run_reports_stone_scale_post_action(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            plan = replace_theme(
                ReplaceRequest(
                    input_spec=self._make_input_spec(
                        board_background_path=board,
                        black_stone_path=black,
                        white_stone_path=white,
                    ),
                    asar_path=root / "app.asar",
                    output_path=root / "out.asar",
                    stone_scale=1.25,
                    dry_run=True,
                )
            )

        self.assertIn(
            "Inject app/js/pandanet-tweaker.js and patch app/index.html to apply stone rendering overrides at runtime.",
            plan.post_actions,
        )
        self.assertIn(
            "Scale all stones by 1.25x around their center.",
            plan.post_actions,
        )

    def test_replace_rejects_out_of_range_stone_scale(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            with self.assertRaisesRegex(ConfigurationError, "must be between 0.1 and 5"):
                replace_theme(
                    ReplaceRequest(
                        input_spec=self._make_input_spec(
                            board_background_path=board,
                            black_stone_path=black,
                            white_stone_path=white,
                        ),
                        asar_path=root / "app.asar",
                        output_path=root / "out.asar",
                        stone_scale=0.05,
                        dry_run=True,
                    )
                )

    def test_replace_rejects_out_of_range_fuzzy_stone_placement(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            board = root / "board.jpg"
            black = root / "black.png"
            white = root / "white.png"
            board.write_bytes(JPEG_1X1)
            black.write_bytes(PNG_1X1)
            white.write_bytes(PNG_1X1)

            with self.assertRaisesRegex(ConfigurationError, "must be between 0 and 0.5"):
                replace_theme(
                    ReplaceRequest(
                        input_spec=self._make_input_spec(
                            board_background_path=board,
                            black_stone_path=black,
                            white_stone_path=white,
                        ),
                        asar_path=root / "app.asar",
                        output_path=root / "out.asar",
                        fuzzy_stone_placement=0.75,
                        dry_run=True,
                    )
                )

    def test_load_input_theme_normalizes_random_stone_variants(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "variant-theme"}', encoding="utf-8")
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
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(PNG_1X1)
            (root / "glass_black2.png").write_bytes(PNG_1X1)
            (root / "glass_black3.png").write_bytes(PNG_1X1)
            (root / "glass_black4.png").write_bytes(PNG_1X1)
            (root / "glass_white3.png").write_bytes(PNG_1X1)
            (root / "glass_white2.png").write_bytes(PNG_1X1)

            theme = load_input_theme(self._make_input_spec(theme_path=root))

        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_BLACK]],
            ["stone-black-variant-1.png", "stone-black-variant-2.png"],
        )
        self.assertEqual(
            [asset.filename for asset in theme.stone_variants[AssetRole.STONE_WHITE]],
            ["stone-white-variant-1.png"],
        )

    def test_build_stone_variant_reference_map_uses_custom_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"name": "variant-theme"}', encoding="utf-8")
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
                .shudan-stone-image.shudan.sign_-1 {
                    background-image: url("glass_white3.png");
                }
                """,
                encoding="utf-8",
            )
            (root / "board.png").write_bytes(PNG_1X1)
            (root / "glass_black2.png").write_bytes(PNG_1X1)
            (root / "glass_black3.png").write_bytes(PNG_1X1)

            theme = load_input_theme(self._make_input_spec(theme_path=root))

        refs = build_stone_variant_reference_map(theme)
        self.assertEqual(
            refs[AssetRole.STONE_BLACK],
            ("img/custom/stone-black-variant-1.png",),
        )

    def test_patch_grid_color_override_appends_goban_scoped_rule(self) -> None:
        with TemporaryDirectory() as temp_dir:
            css_path = Path(temp_dir) / "site.css"
            css_path.write_text(".goban-page .goban canvas.grid-canvas {\n  z-index: 1;\n}\n", encoding="utf-8")

            patch_grid_color_override(css_path, grid_rgba_to_css_filter("#336699cc"))
            css_text = css_path.read_text(encoding="utf-8")

        self.assertIn("/* pandanet-tweaker grid override */", css_text)
        self.assertIn(".goban > .grid-canvas {", css_text)
        self.assertIn("filter: ", css_text)
        self.assertIn("opacity: 0.8;", css_text)

if __name__ == "__main__":
    unittest.main()
