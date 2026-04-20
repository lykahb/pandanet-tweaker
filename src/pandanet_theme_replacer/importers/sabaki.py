from __future__ import annotations

from pathlib import Path
import json
import re
from urllib.parse import urlsplit

from pandanet_theme_replacer.errors import ThemeImportError
from pandanet_theme_replacer.models import (
    AssetRole,
    EXPECTED_THEME_ROLES,
    ImportedTheme,
    StoneTransform,
    ThemeAsset,
)
from pandanet_theme_replacer.theme_sources import PreparedThemeSource

URL_PATTERN = re.compile(r"url\((?P<quote>['\"]?)(?P<path>.+?)(?P=quote)\)")
CSS_RULE_PATTERN = re.compile(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", re.DOTALL)
CSS_DECLARATION_PATTERN = re.compile(r"(?P<name>[-\w]+)\s*:\s*(?P<value>[^;]+)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
CSS_CANDIDATES = ("theme.css", "styles.css", "index.css")
STONE_SELECTORS: dict[AssetRole, str] = {
    AssetRole.STONE_BLACK: ".shudan-stone-image.shudan-sign_1",
    AssetRole.STONE_WHITE: ".shudan-stone-image.shudan-sign_-1",
}
STONE_RANDOM_SELECTOR_PATTERN = re.compile(r"\.shudan-random_(\d+)\b")
TRANSFORM_PROPERTIES = ("width", "height", "top", "left")


def load_sabaki_theme(prepared: PreparedThemeSource) -> ImportedTheme:
    theme_root = _discover_theme_root(prepared.staged_root)
    package_data = _load_package_json(theme_root)
    css_path = _find_css_path(theme_root)
    warnings: list[str] = []

    assets = _collect_assets(theme_root, css_path)
    stone_transforms = _extract_stone_transforms(css_path)
    stone_variants = _extract_stone_variants(theme_root, css_path)

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
        stone_transforms=stone_transforms,
        stone_variants=stone_variants,
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
    role_specific_paths: set[str] = set()

    if css_path is not None:
        for asset in _extract_role_assets_from_css(theme_root, css_path):
            discovered[f"{asset.role.value}:{asset.source_ref}"] = asset
            role_specific_paths.add(asset.source_ref)
        for relative_path in _parse_css_asset_paths(css_path):
            candidate = (css_path.parent / relative_path).resolve()
            if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES:
                asset = _build_asset(theme_root, candidate)
                if asset.role == AssetRole.UNKNOWN or asset.source_ref in role_specific_paths:
                    continue
                discovered[asset.source_ref] = asset

    for candidate in theme_root.glob("**/*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        asset = _build_asset(theme_root, candidate)
        if asset.role == AssetRole.UNKNOWN or asset.source_ref in role_specific_paths:
            continue
        discovered.setdefault(asset.source_ref, asset)

    assets = list(discovered.values())
    assets.sort(key=lambda asset: (asset.role.value, asset.filename))
    return assets


def _extract_role_assets_from_css(theme_root: Path, css_path: Path) -> list[ThemeAsset]:
    discovered: dict[str, ThemeAsset] = {}
    css_text = css_path.read_text(encoding="utf-8")

    for selectors, declarations in _parse_css_rules(css_text):
        if any(_extract_random_variant_role(selector) is not None for selector in selectors):
            continue
        roles = [role for role, selector in STONE_SELECTORS.items() if selector in selectors]
        if not roles:
            continue

        background_image = _extract_background_image(declarations)
        if background_image is None:
            continue

        candidate = (css_path.parent / background_image).resolve()
        if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        for role in roles:
            asset = _build_asset(theme_root, candidate, role=role, notes="css-role-match")
            discovered[f"{role.value}:{asset.source_ref}"] = asset

    return list(discovered.values())


def _extract_stone_variants(theme_root: Path, css_path: Path | None) -> dict[AssetRole, tuple[ThemeAsset, ...]]:
    if css_path is None:
        return {}

    discovered: dict[AssetRole, list[tuple[int, ThemeAsset]]] = {}
    css_text = css_path.read_text(encoding="utf-8")
    for selectors, declarations in _parse_css_rules(css_text):
        role_and_index = None
        for selector in selectors:
            role_and_index = _extract_random_variant_role(selector)
            if role_and_index is not None:
                break
        if role_and_index is None:
            continue

        background_image = _extract_background_image(declarations)
        if background_image is None:
            continue

        candidate = (css_path.parent / background_image).resolve()
        if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        role, index = role_and_index
        asset = _build_asset(
            theme_root,
            candidate,
            role=role,
            notes=f"css-random-variant:{index}",
        )
        discovered.setdefault(role, []).append((index, asset))

    return {
        role: tuple(
            asset
            for index, asset in sorted(entries, key=lambda item: (item[0], item[1].source_ref))
        )
        for role, entries in discovered.items()
    }


def _parse_css_asset_paths(css_path: Path) -> list[Path]:
    paths: list[Path] = []
    css_text = css_path.read_text(encoding="utf-8")

    for match in URL_PATTERN.finditer(css_text):
        raw_path = match.group("path").strip()
        if not raw_path or raw_path.startswith(("data:", "http://", "https://")):
            continue
        cleaned_path = _sanitize_css_asset_path(raw_path)
        if cleaned_path is not None:
            paths.append(cleaned_path)

    return paths


def _sanitize_css_asset_path(raw_path: str) -> Path | None:
    parsed = urlsplit(raw_path)
    cleaned = parsed.path.strip()
    if not cleaned:
        return None
    return Path(cleaned)


def _build_asset(
    theme_root: Path,
    path: Path,
    *,
    role: AssetRole | None = None,
    notes: str | None = None,
) -> ThemeAsset:
    relative_path = path.relative_to(theme_root)
    return ThemeAsset(
        role=role or _classify_role(relative_path),
        filename=path.name,
        source_ref=relative_path.as_posix(),
        data=path.read_bytes(),
        notes=notes,
    )


def _classify_role(relative_path: Path) -> AssetRole:
    name = relative_path.as_posix().lower()

    if any(token in name for token in ("black", "dark")) and not any(
        token in name for token in ("white", "light")
    ):
        return AssetRole.STONE_BLACK
    if any(token in name for token in ("white", "light")):
        return AssetRole.STONE_WHITE
    if any(token in name for token in ("board", "goban", "wood", "grain", "kaya", "bamboo")):
        return AssetRole.BOARD
    if any(token in name for token in ("background", "bg")):
        return AssetRole.BOARD

    return AssetRole.UNKNOWN


def _extract_stone_transforms(css_path: Path | None) -> dict[AssetRole, StoneTransform]:
    if css_path is None:
        return {}

    transforms: dict[AssetRole, StoneTransform] = {}
    css_text = css_path.read_text(encoding="utf-8")
    for selectors, declarations in _parse_css_rules(css_text):
        for role, selector in STONE_SELECTORS.items():
            if selector in selectors:
                transform = _extract_stone_transform(declarations)
                if transform is not None:
                    transforms[role] = transform

    return transforms


def _extract_random_variant_role(selector: str) -> tuple[AssetRole, int] | None:
    random_match = STONE_RANDOM_SELECTOR_PATTERN.search(selector)
    if random_match is None:
        return None

    for role, base_selector in STONE_SELECTORS.items():
        if base_selector in selector:
            return (role, int(random_match.group(1)))

    return None


def _parse_css_rules(css_text: str) -> list[tuple[list[str], dict[str, str]]]:
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    rules: list[tuple[list[str], dict[str, str]]] = []
    for match in CSS_RULE_PATTERN.finditer(css_text):
        selector_text = match.group("selectors")
        body = match.group("body")
        selectors = [selector.strip() for selector in selector_text.split(",") if selector.strip()]
        if not selectors:
            continue

        declarations: dict[str, str] = {}
        for declaration in CSS_DECLARATION_PATTERN.finditer(body):
            declarations[declaration.group("name").strip().lower()] = declaration.group("value").strip()
        rules.append((selectors, declarations))
    return rules


def _extract_stone_transform(declarations: dict[str, str]) -> StoneTransform | None:
    values: dict[str, str] = {}
    for name in TRANSFORM_PROPERTIES:
        value = declarations.get(name)
        if value is None:
            return None
        normalized = _normalize_percentage(value)
        if normalized is None:
            return None
        values[name] = normalized

    return StoneTransform(
        width=values["width"],
        height=values["height"],
        top=values["top"],
        left=values["left"],
    )


def _extract_background_image(declarations: dict[str, str]) -> Path | None:
    value = declarations.get("background-image")
    if value is None:
        return None

    match = URL_PATTERN.search(value)
    if match is None:
        return None

    raw_path = match.group("path").strip()
    if not raw_path or raw_path.startswith(("data:", "http://", "https://")):
        return None

    return _sanitize_css_asset_path(raw_path)


def _normalize_percentage(value: str) -> str | None:
    compact = re.sub(r"\s+", "", value)
    if re.fullmatch(r"-?\d+(?:\.\d+)?%", compact) is None:
        return None
    return compact
