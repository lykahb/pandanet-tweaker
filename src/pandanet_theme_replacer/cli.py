from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pandanet_theme_replacer.errors import PandanetThemeReplacerError
from pandanet_theme_replacer.models import BackgroundMode, ReplaceRequest, ThemeInputSpec
from pandanet_theme_replacer.pipeline import inspect_theme, replace_theme
from pandanet_theme_replacer.targets.pandanet import resolve_source_asar_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pandanet-theme-replacer",
        description="Inspect Sabaki themes and repack Pandanet app.asar with replacement assets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect-theme", help="Inspect a theme package and print the detected assets."
    )
    inspect_parser.add_argument("theme", type=Path, help="Path to a Sabaki theme directory or zip.")
    inspect_parser.add_argument(
        "--format", choices=("auto", "sabaki"), default="auto", help="Theme input format."
    )

    replace_parser = subparsers.add_parser(
        "replace",
        help="Build a replacement plan and optionally repack a new app.asar.",
    )
    replace_parser.add_argument(
        "theme",
        nargs="?",
        type=Path,
        help="Optional path to a Sabaki theme directory or zip.",
    )
    replace_parser.add_argument(
        "--asar",
        type=Path,
        help="Source Pandanet ASAR path. Defaults to original-app.asar when present, otherwise app.asar.",
    )
    replace_parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/app.asar"),
        help="Output path for the repacked app.asar.",
    )
    replace_parser.add_argument(
        "--cache-asar-dir",
        type=Path,
        help="Persistent extracted ASAR cache directory for repeated theme testing. Use this when you plan to apply multiple themes over time and want to avoid unpacking the source ASAR on every run.",
    )
    replace_parser.add_argument(
        "--format", choices=("auto", "sabaki"), default="auto", help="Theme input format."
    )
    replace_parser.add_argument(
        "--board-background",
        dest="board_background",
        type=Path,
        help="Override the board texture used inside the goban. The source file is copied into the patched ASAR as-is.",
    )
    replace_parser.add_argument(
        "--board-background-mode",
        dest="board_background_mode",
        choices=tuple(mode.value for mode in BackgroundMode),
        help="How the goban board texture should be rendered inside the client.",
    )
    replace_parser.add_argument(
        "--black-stone",
        type=Path,
        help="Override the black stone asset. The source file is copied into the patched ASAR as-is.",
    )
    replace_parser.add_argument(
        "--white-stone",
        type=Path,
        help="Override the white stone asset. The source file is copied into the patched ASAR as-is.",
    )
    replace_parser.add_argument(
        "--grid-rgba",
        type=str,
        help="Tint the goban grid canvas with a hex RGBA color, for example #c58a3cff.",
    )
    replace_parser.add_argument(
        "--fuzzy-stone-placement",
        type=float,
        default=0.0,
        help=(
            "Apply Shudan-style fuzzy stone placement. The value is a fraction of the "
            "drawn stone diameter and must be between 0 and 0.5."
        ),
    )
    replace_parser.add_argument(
        "--disable-default-shadows",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Hide Pandanet's stock shadow canvas. Enabled by default because the built-in "
            "shadows often clash with custom themes and fuzzy stone placement."
        ),
    )
    replace_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the replacement plan without extracting or repacking the ASAR.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect-theme":
            theme = inspect_theme(args.theme, theme_format=args.format)
            _print_theme_summary(theme)
            return 0

        if args.command == "replace":
            background_mode = (
                BackgroundMode(args.board_background_mode)
                if args.board_background_mode is not None
                else None
            )
            asar_path = resolve_source_asar_path(args.asar)
            request = ReplaceRequest(
                input_spec=ThemeInputSpec(
                    theme_path=args.theme,
                    theme_format=args.format,
                    board_background_path=args.board_background,
                    black_stone_path=args.black_stone,
                    white_stone_path=args.white_stone,
                ),
                asar_path=asar_path,
                output_path=args.output,
                cache_asar_dir=args.cache_asar_dir,
                background_mode=background_mode,
                grid_rgba=args.grid_rgba,
                fuzzy_stone_placement=args.fuzzy_stone_placement,
                disable_default_shadows=args.disable_default_shadows,
                dry_run=args.dry_run,
            )
            plan = replace_theme(request)
            _print_replacement_plan(plan, asar_path, args.output, args.dry_run)
            return 0

        parser.error("Unknown command")
        return 2
    except PandanetThemeReplacerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _print_theme_summary(theme) -> None:
    print(f"Theme: {theme.name}")
    print(f"Format: {theme.format_name}")
    print(f"Source: {theme.source}")
    if theme.version:
        print(f"Version: {theme.version}")
    print("Assets:")
    for asset in theme.assets:
        print(f"- {asset.role.value}: {asset.source_ref} ({asset.size} bytes)")
    if theme.stone_variants:
        print("Stone Variants:")
        for role, assets in theme.stone_variants.items():
            for asset in assets:
                print(f"- {role.value}-variant: {asset.source_ref} ({asset.size} bytes)")
    if theme.warnings:
        print("Warnings:")
        for warning in theme.warnings:
            print(f"- {warning}")


def _print_replacement_plan(plan, asar_path: Path, output_path: Path, dry_run: bool) -> None:
    print(f"Theme: {plan.theme.name}")
    print(f"ASAR: {asar_path}")
    print(f"Output: {output_path}")
    print(f"Mode: {'dry-run' if dry_run else 'replace'}")
    print("Plan:")
    for operation in plan.operations:
        source_ref = operation.source_asset.source_ref if operation.source_asset else "missing"
        target_ref = str(operation.target_relative_path) if operation.target_relative_path else "missing"
        print(
            f"- {operation.role.value}: {operation.status} | source={source_ref} | "
            f"target={target_ref} | {operation.reason}"
        )
    if plan.post_actions:
        print("Post-actions:")
        for action in plan.post_actions:
            print(f"- {action}")
