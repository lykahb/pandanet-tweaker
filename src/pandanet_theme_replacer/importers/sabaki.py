from __future__ import annotations

from pathlib import Path
import json
import re

from pandanet_theme_replacer.errors import ThemeImportError
from pandanet_theme_replacer.models import (
    AssetRole,
    EXPECTED_THEME_ROLES,
    ImportedTheme,
    ThemeAsset,
)
from pandanet_theme_replacer.theme_sources import PreparedThemeSource

URL_PATTERN = re.compile(r"url\((?P<quote>['\"]?)(?P<path>.+?)(?P=quote)\)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
CSS_CANDIDATES = ("theme.css", "styles.css", "index.css")


def load_sabaki_theme(prepared: PreparedThemeSource) -> ImportedTheme:
    theme_root = _discover_theme_root(prepared.staged_root)
    package_data = _load_package_json(theme_root)
    css_path = _find_css_path(theme_root)
    warnings: list[str] = []

    assets = _collect_assets(theme_root, css_path)

    for role in EXPECTED_THEME_ROLES:
        if not any(asset.role == role for asset in assets):
            warnings.append(f"Missing detected asset for role '{role.value}'.")

    metadata = {
        "package_json": str(theme_root / "package.json"),
    }
    if css_path is not None:
        metadata["theme_css"] = str(css_path)

    return ImportedTheme(
        source=prepared.source_path,
        root=theme_root,
        format_name="sabaki",
        name=package_data.get("name", theme_root.name),
        version=package_data.get("version"),
        assets=tuple(assets),
        warnings=tuple(warnings),
        metadata=metadata,
    )


def _discover_theme_root(staged_root: Path) -> Path:
    direct = staged_root / "package.json"
    if direct.is_file():
        return staged_root

    candidates = sorted(
        staged_root.glob("**/package.json"),
        key=lambda path: (len(path.relative_to(staged_root).parts), str(path)),
    )
    if not candidates:
        raise ThemeImportError(
            "Sabaki theme detection failed: no package.json found in the theme source."
        )

    return candidates[0].parent


def _load_package_json(theme_root: Path) -> dict[str, object]:
    package_path = theme_root / "package.json"
    try:
        return json.loads(package_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ThemeImportError(f"Missing package.json in theme root: {theme_root}") from exc
    except json.JSONDecodeError as exc:
        raise ThemeImportError(f"Invalid package.json in theme root: {theme_root}") from exc


def _find_css_path(theme_root: Path) -> Path | None:
    for candidate in CSS_CANDIDATES:
        path = theme_root / candidate
        if path.is_file():
            return path
    return None


def _collect_assets(theme_root: Path, css_path: Path | None) -> list[ThemeAsset]:
    discovered: dict[str, ThemeAsset] = {}

    if css_path is not None:
        for relative_path in _parse_css_asset_paths(css_path):
            candidate = (css_path.parent / relative_path).resolve()
            if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES:
                asset = _build_asset(theme_root, candidate)
                discovered[asset.source_ref] = asset

    for candidate in theme_root.glob("**/*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        asset = _build_asset(theme_root, candidate)
        if asset.role == AssetRole.UNKNOWN:
            continue
        discovered.setdefault(asset.source_ref, asset)

    assets = list(discovered.values())
    assets.sort(key=lambda asset: (asset.role.value, asset.filename))
    return assets


def _parse_css_asset_paths(css_path: Path) -> list[Path]:
    paths: list[Path] = []
    css_text = css_path.read_text(encoding="utf-8")

    for match in URL_PATTERN.finditer(css_text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("data:", "http://", "https://")):
            continue
        paths.append(Path(raw_path))

    return paths


def _build_asset(theme_root: Path, path: Path) -> ThemeAsset:
    relative_path = path.relative_to(theme_root)
    return ThemeAsset(
        role=_classify_role(relative_path),
        filename=path.name,
        source_ref=relative_path.as_posix(),
        data=path.read_bytes(),
    )


def _classify_role(relative_path: Path) -> AssetRole:
    name = relative_path.as_posix().lower()

    if "black" in name and "white" not in name:
        return AssetRole.STONE_BLACK
    if "white" in name:
        return AssetRole.STONE_WHITE
    if any(token in name for token in ("board", "wood", "grain", "kaya", "bamboo", "bg", "background", "goban")):
        return AssetRole.BOARD

    return AssetRole.UNKNOWN
