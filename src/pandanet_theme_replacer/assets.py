from __future__ import annotations

from pathlib import Path

from pandanet_theme_replacer.errors import ThemeImportError
from pandanet_theme_replacer.models import ImportedTheme, ThemeAsset, AssetRole


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

    source_root = _common_source_root(
        [
            asset_path
            for asset_path in (background_path, black_stone_path, white_stone_path)
            if asset_path is not None
        ]
    )

    return ImportedTheme(
        source=source_root,
        root=source_root,
        format_name="explicit-assets",
        name="custom-assets",
        version=None,
        assets=tuple(assets),
        stone_transforms={},
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
        stone_transforms=dict(base_theme.stone_transforms),
        warnings=base_theme.warnings,
        metadata=metadata,
    )


def normalize_theme_assets(theme: ImportedTheme) -> ImportedTheme:
    normalized_assets = tuple(_normalize_theme_asset(asset) for asset in theme.assets)
    metadata = dict(theme.metadata)
    metadata["normalized_for_targets"] = "true"

    return ImportedTheme(
        source=theme.source,
        root=theme.root,
        format_name=theme.format_name,
        name=theme.name,
        version=theme.version,
        assets=normalized_assets,
        stone_transforms=dict(theme.stone_transforms),
        warnings=theme.warnings,
        metadata=metadata,
    )


def _load_asset(role: AssetRole, source_path: Path) -> ThemeAsset:
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise ThemeImportError(f"Asset file does not exist: {source_path}")

    return ThemeAsset(
        role=role,
        filename=_normalized_filename(role, source_path.name),
        source_ref=str(source_path),
        data=source_path.read_bytes(),
        notes="original-bytes",
    )


def _normalize_theme_asset(asset: ThemeAsset) -> ThemeAsset:
    normalized_filename = _normalized_filename(asset.role, asset.filename)
    return ThemeAsset(
        role=asset.role,
        filename=normalized_filename,
        source_ref=asset.source_ref,
        data=asset.data,
        notes=asset.notes or "original-bytes",
    )


def _normalized_filename(role: AssetRole, original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    if not suffix:
        suffix = ".bin"

    if role == AssetRole.BOARD:
        base = "board"
    elif role == AssetRole.STONE_BLACK:
        base = "stone-black"
    elif role == AssetRole.STONE_WHITE:
        base = "stone-white"
    else:
        base = Path(original_name).stem

    return f"{base}{suffix}"


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
