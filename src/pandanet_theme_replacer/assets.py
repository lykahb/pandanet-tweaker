from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from pandanet_theme_replacer.errors import ExternalToolError, ThemeImportError
from pandanet_theme_replacer.models import AssetRole, ImportedTheme, ThemeAsset
from pandanet_theme_replacer.targets.pandanet import PANDANET_TARGET_FORMATS


def build_theme_from_asset_files(
    *,
    background_path: Path | None,
    black_stone_path: Path | None,
    white_stone_path: Path | None,
) -> ImportedTheme:
    assets: list[ThemeAsset] = []

    if background_path is not None:
        assets.append(_load_asset(AssetRole.BOARD, background_path))
    if black_stone_path is not None:
        assets.append(_load_asset(AssetRole.STONE_BLACK, black_stone_path))
    if white_stone_path is not None:
        assets.append(_load_asset(AssetRole.STONE_WHITE, white_stone_path))

    if not assets:
        raise ThemeImportError(
            "No input assets were provided. Pass a theme, or provide --board-background, "
            "--black-stone, and --white-stone inputs."
        )

    source_root = _common_source_root([asset_path for asset_path in (background_path, black_stone_path, white_stone_path) if asset_path is not None])

    return ImportedTheme(
        source=source_root,
        root=source_root,
        format_name="explicit-assets",
        name="custom-assets",
        version=None,
        assets=tuple(assets),
        metadata={},
    )


def merge_theme_assets(base_theme: ImportedTheme, overrides: ImportedTheme) -> ImportedTheme:
    ordered_assets = list(base_theme.assets)
    seen_roles = {asset.role for asset in ordered_assets}
    for asset in overrides.assets:
        if asset.role in seen_roles:
            for index, existing in enumerate(ordered_assets):
                if existing.role == asset.role:
                    ordered_assets[index] = asset
                    break
        else:
            ordered_assets.append(asset)
            seen_roles.add(asset.role)

    metadata = dict(base_theme.metadata)
    metadata["asset_overrides"] = "true"

    return ImportedTheme(
        source=base_theme.source,
        root=base_theme.root,
        format_name=base_theme.format_name,
        name=base_theme.name,
        version=base_theme.version,
        assets=tuple(ordered_assets),
        warnings=base_theme.warnings,
        metadata=metadata,
    )


def _load_asset(role: AssetRole, source_path: Path) -> ThemeAsset:
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise ThemeImportError(f"Asset file does not exist: {source_path}")

    target_format = PANDANET_TARGET_FORMATS[role]
    data = convert_image_for_role(source_path, role)

    return ThemeAsset(
        role=role,
        filename=f"{source_path.stem}.{_suffix_for_format(target_format)}",
        source_ref=str(source_path),
        data=data,
        notes=f"converted-to-{target_format}",
    )


def convert_image_for_role(source_path: Path, role: AssetRole) -> bytes:
    target_format = PANDANET_TARGET_FORMATS[role]
    if source_path.suffix.lower() in _accepted_suffixes(target_format):
        return source_path.read_bytes()

    with TemporaryDirectory(prefix="pandanet-convert-") as temp_dir:
        temp_root = Path(temp_dir)
        output_path = temp_root / f"converted.{_suffix_for_format(target_format)}"
        command = ["sips", "-s", "format", target_format, str(source_path), "--out", str(output_path)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise ExternalToolError(f"Image conversion failed: {' '.join(command)}\n{detail}")
        return output_path.read_bytes()


def _accepted_suffixes(target_format: str) -> tuple[str, ...]:
    if target_format == "jpeg":
        return (".jpg", ".jpeg")
    if target_format == "png":
        return (".png",)
    return (f".{target_format}",)


def _suffix_for_format(target_format: str) -> str:
    if target_format == "jpeg":
        return "jpg"
    return target_format


def _common_source_root(paths: list[Path]) -> Path:
    resolved = [path.expanduser().resolve() for path in paths]
    if not resolved:
        return Path.cwd()
    if len(resolved) == 1:
        return resolved[0].parent
    common = Path(resolved[0].parent)
    for path in resolved[1:]:
        while common != common.parent and common not in path.parents and common != path.parent:
            common = common.parent
    return common
