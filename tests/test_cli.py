from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_tweaker.cli import _expand_variant_paths, _print_next_steps, _print_replacement_plan, build_parser
from pandanet_tweaker.errors import ConfigurationError
from pandanet_tweaker.models import AssetRole, ImportedTheme, PlannedReplacement, ReplacementPlan, ThemeAsset


class CliOutputTests(unittest.TestCase):
    def test_print_next_steps_points_to_installed_app_and_original_archive(self) -> None:
        buffer = StringIO()

        with redirect_stdout(buffer):
            _print_next_steps(
                Path("C:/Users/alice/AppData/Local/Programs/GoPanda2/resources/original-app.asar"),
                Path("build/app.asar"),
            )

        output = buffer.getvalue()
        self.assertIn("Next Steps:", output)
        self.assertIn(
            "replace C:/Users/alice/AppData/Local/Programs/GoPanda2/resources/app.asar with",
            output,
        )
        self.assertIn("original-app.asar", output)
        self.assertNotIn("Patched archive:", output)

    def test_print_next_steps_uses_generic_message_for_nonstandard_source_archive(self) -> None:
        buffer = StringIO()

        with redirect_stdout(buffer):
            _print_next_steps(Path("original-win-app.asar"), Path("build/app.asar"))

        output = buffer.getvalue()
        self.assertIn("Patched archive:", output)
        self.assertIn("Keep a clean original-app.asar next to the installed app.asar", output)

    def test_print_replacement_plan_hides_details_without_verbose(self) -> None:
        buffer = StringIO()
        plan = _sample_plan()

        with redirect_stdout(buffer):
            _print_replacement_plan(
                plan,
                Path("source.asar"),
                Path("build/app.asar"),
                False,
                verbose=False,
            )

        output = buffer.getvalue()
        self.assertIn("Theme: sample-theme", output)
        self.assertIn("Output: build/app.asar", output)
        self.assertNotIn("Plan:", output)
        self.assertNotIn("Post-actions:", output)

    def test_print_replacement_plan_shows_details_with_verbose(self) -> None:
        buffer = StringIO()
        plan = _sample_plan()

        with redirect_stdout(buffer):
            _print_replacement_plan(
                plan,
                Path("source.asar"),
                Path("build/app.asar"),
                True,
                verbose=True,
            )

        output = buffer.getvalue()
        self.assertIn("Plan:", output)
        self.assertIn("Post-actions:", output)
        self.assertIn("board: ready", output)

    def test_replace_parser_accepts_grouped_and_repeated_explicit_stone_variants(self) -> None:
        args = build_parser().parse_args(
            [
                "replace",
                "--board-background",
                "board.png",
                "--black-stone",
                "black.png",
                "--black-stone-variant",
                "black-1.png",
                "black-2.png",
                "--black-stone-variant",
                "black-3.png",
                "--white-stone",
                "white.png",
                "--white-stone-variant",
                "white-1.png",
                "white-2.png",
            ]
        )

        self.assertEqual(_expand_variant_paths(args.black_stone_variants), (Path("black-1.png"), Path("black-2.png"), Path("black-3.png")))
        self.assertEqual(_expand_variant_paths(args.white_stone_variants), (Path("white-1.png"), Path("white-2.png")))

    def test_replace_parser_accepts_baked_grid_background_pair(self) -> None:
        args = build_parser().parse_args(
            [
                "replace",
                "--board-background-with-grid",
                "board-grid.png",
                "--board-background-with-grid-and-coordinates",
                "board-grid-coordinates.png",
                "--black-stone",
                "black.png",
                "--white-stone",
                "white.png",
            ]
        )

        self.assertEqual(args.board_background_with_grid, Path("board-grid.png"))
        self.assertEqual(
            args.board_background_with_grid_and_coordinates,
            Path("board-grid-coordinates.png"),
        )

    def test_expand_variant_paths_expands_quoted_globs_in_sorted_order(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "stone-white-1.png"
            second = root / "stone-white-2.png"
            ignored = root / "stone-black-1.png"
            second.write_bytes(b"second")
            ignored.write_bytes(b"ignored")
            first.write_bytes(b"first")

            paths = _expand_variant_paths([[root / "stone-white-*.png"]])

        self.assertEqual(paths, (first, second))

    def test_expand_variant_paths_rejects_unmatched_quoted_glob(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pattern = Path(temp_dir) / "missing-*.png"

            with self.assertRaisesRegex(ConfigurationError, "did not match any files"):
                _expand_variant_paths([[pattern]])


def _sample_plan() -> ReplacementPlan:
    asset = ThemeAsset(
        role=AssetRole.BOARD,
        filename="board.jpg",
        source_ref="board.jpg",
        data=b"board",
    )
    theme = ImportedTheme(
        source=Path("theme.asar"),
        root=Path("theme"),
        format_name="sabaki",
        name="sample-theme",
        version=None,
        assets=(asset,),
    )
    operation = PlannedReplacement(
        role=AssetRole.BOARD,
        source_asset=asset,
        target_relative_path=Path("app/img/custom/board.jpg"),
        status="ready",
        reason="Ready to replace.",
    )
    return ReplacementPlan(
        theme=theme,
        operations=(operation,),
        post_actions=("Patch app/js/gopanda.js.",),
    )


if __name__ == "__main__":
    unittest.main()
