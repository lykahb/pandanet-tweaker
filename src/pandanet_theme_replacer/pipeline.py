from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pandanet_theme_replacer.assets import build_theme_from_asset_files, merge_theme_assets
from pandanet_theme_replacer.errors import ConfigurationError, ThemeImportError
from pandanet_theme_replacer.importers.sabaki import load_sabaki_theme
from pandanet_theme_replacer.models import (
    BackgroundMode,
    EXPECTED_THEME_ROLES,
    ImportedTheme,
    PlannedReplacement,
    ReplacementPlan,
)
from pandanet_theme_replacer.packaging.asar import extract_asar, pack_asar
from pandanet_theme_replacer.targets.pandanet import PANDANET_SITE_CSS_PATH, PANDANET_THEME_TARGETS
from pandanet_theme_replacer.theme_sources import stage_theme_source

GOBAN_BLOCK_PATTERN = re.compile(r"(?P<prefix>\.goban\s*\{)(?P<body>.*?)(?P<suffix>\n\})", re.DOTALL)


def inspect_theme(theme_path: Path, theme_format: str = "auto") -> ImportedTheme:
    with stage_theme_source(theme_path) as prepared:
        return _load_theme(prepared, theme_format)


def build_replacement_plan(
    theme: ImportedTheme,
    *,
    background_mode: BackgroundMode | None = None,
) -> ReplacementPlan:
    operations: list[PlannedReplacement] = []
    post_actions: list[str] = []

    for role in EXPECTED_THEME_ROLES:
        source_asset = theme.first_asset_for_role(role)
        target_path = PANDANET_THEME_TARGETS.get(role)

        if source_asset is None:
            operations.append(
                PlannedReplacement(
                    role=role,
                    source_asset=None,
                    target_relative_path=target_path,
                    status="missing-source",
                    reason="No matching asset was detected in the imported theme.",
                )
            )
            continue

        if target_path is None:
            operations.append(
                PlannedReplacement(
                    role=role,
                    source_asset=source_asset,
                    target_relative_path=None,
                    status="missing-target",
                    reason="Pandanet target mapping has not been configured yet.",
                )
            )
            continue

        operations.append(
            PlannedReplacement(
                role=role,
                source_asset=source_asset,
                target_relative_path=target_path,
                status="ready",
                reason="Ready to replace.",
            )
        )

    if background_mode is not None:
        post_actions.append(f"Patch {PANDANET_SITE_CSS_PATH} to set board background mode to '{background_mode.value}'.")

    return ReplacementPlan(theme=theme, operations=tuple(operations), post_actions=tuple(post_actions))


def replace_theme(
    theme_path: Path | None,
    asar_path: Path,
    output_path: Path,
    *,
    background_path: Path | None = None,
    black_stone_path: Path | None = None,
    white_stone_path: Path | None = None,
    background_mode: BackgroundMode | None = None,
    dry_run: bool = False,
    theme_format: str = "auto",
) -> ReplacementPlan:
    theme = load_input_theme(
        theme_path,
        theme_format=theme_format,
        background_path=background_path,
        black_stone_path=black_stone_path,
        white_stone_path=white_stone_path,
    )
    plan = build_replacement_plan(theme, background_mode=background_mode)

    if dry_run:
        return plan

    unresolved = [operation for operation in plan.operations if operation.status != "ready"]
    if unresolved:
        raise ConfigurationError(
            "Replacement plan is incomplete. Provide board, black stone, and white stone assets "
            "through a theme or explicit file arguments."
        )

    asar_path = asar_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    if not asar_path.is_file():
        raise ThemeImportError(f"ASAR file does not exist: {asar_path}")

    with TemporaryDirectory(prefix="pandanet-asar-") as temp_dir:
        temp_root = Path(temp_dir)
        extracted_dir = temp_root / "app"
        extract_asar(asar_path, extracted_dir)

        for operation in plan.operations:
            assert operation.source_asset is not None
            assert operation.target_relative_path is not None

            destination = extracted_dir / operation.target_relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(operation.source_asset.data)

        if background_mode is not None:
            patch_background_mode(extracted_dir / PANDANET_SITE_CSS_PATH, background_mode)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pack_asar(extracted_dir, output_path)

    return plan


def load_input_theme(
    theme_path: Path | None,
    *,
    theme_format: str = "auto",
    background_path: Path | None = None,
    black_stone_path: Path | None = None,
    white_stone_path: Path | None = None,
) -> ImportedTheme:
    explicit_assets = None
    if any(path is not None for path in (background_path, black_stone_path, white_stone_path)):
        explicit_assets = build_theme_from_asset_files(
            background_path=background_path,
            black_stone_path=black_stone_path,
            white_stone_path=white_stone_path,
        )

    if theme_path is None:
        if explicit_assets is None:
            raise ThemeImportError(
                "No input theme or assets were provided. Supply a theme path or explicit asset arguments."
            )
        return explicit_assets

    with stage_theme_source(theme_path) as prepared:
        theme = _load_theme(prepared, theme_format)

    if explicit_assets is None:
        return theme
    return merge_theme_assets(theme, explicit_assets)


def _load_theme(prepared, theme_format: str) -> ImportedTheme:
    if theme_format not in {"auto", "sabaki"}:
        raise ThemeImportError(f"Unsupported theme format: {theme_format}")

    return load_sabaki_theme(prepared)


def patch_background_mode(site_css_path: Path, mode: BackgroundMode) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")
    match = GOBAN_BLOCK_PATTERN.search(css_text)
    if match is None:
        raise ConfigurationError(f"Could not find .goban CSS block in {site_css_path}")

    body = match.group("body")
    lines = body.splitlines()
    filtered_lines = [
        line for line in lines if "background-size:" not in line and "background-position:" not in line
    ]

    replacement_lines: list[str] = []
    replaced_background = False
    for line in filtered_lines:
        if 'background: url("../img/wood-board.jpg")' in line:
            if mode == BackgroundMode.REPEAT:
                replacement_lines.append('  background: url("../img/wood-board.jpg") repeat;')
            else:
                replacement_lines.append('  background: url("../img/wood-board.jpg") no-repeat;')
                replacement_lines.append("  background-size: 100% 100%;")
                replacement_lines.append("  background-position: center;")
            replaced_background = True
        else:
            replacement_lines.append(line)

    if not replaced_background:
        raise ConfigurationError(f"Could not find wood-board background declaration in {site_css_path}")

    new_block = f"{match.group('prefix')}{''.join(f'{line}\n' for line in replacement_lines)}{match.group('suffix')}"
    site_css_path.write_text(css_text[: match.start()] + new_block + css_text[match.end() :], encoding="utf-8")
