from __future__ import annotations

from pathlib import Path

from pandanet_theme_replacer.models import AssetRole, ThemeAsset

DEFAULT_ASAR_DIR = Path("/Applications/GoPanda2.app/Contents/Resources")
DEFAULT_ASAR_PATH = Path("/Applications/GoPanda2.app/Contents/Resources/app.asar")
DEFAULT_ORIGINAL_ASAR_PATH = Path("/Applications/GoPanda2.app/Contents/Resources/original-app.asar")
PANDANET_SITE_CSS_PATH = Path("app/css/site.css")
PANDANET_GOPANDA_JS_PATH = Path("app/js/gopanda.js")
PANDANET_CUSTOM_ASSET_DIR = Path("app/img/custom")

PANDANET_THEME_STOCK_REFS: dict[AssetRole, str] = {
    AssetRole.BOARD: "../img/wood-board.jpg",
    AssetRole.STONE_BLACK: "img/50/stone-black.png",
    AssetRole.STONE_WHITE: "img/50/stone-white.png",
}

PANDANET_CSS_REF_REPLACEMENTS: dict[str, AssetRole] = {
    "../img/wood-board.jpg": AssetRole.BOARD,
    "../img/50/stone-black-w-shadow.png": AssetRole.STONE_BLACK,
    "../img/50/stone-white-w-shadow.png": AssetRole.STONE_WHITE,
    "../img/50/stone-black.png": AssetRole.STONE_BLACK,
    "../img/50/stone-white.png": AssetRole.STONE_WHITE,
}

PANDANET_JS_REF_REPLACEMENTS: dict[str, AssetRole] = {
    "img/50/stone-black.png": AssetRole.STONE_BLACK,
    "img/50/stone-white.png": AssetRole.STONE_WHITE,
}


def resolve_source_asar_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        return explicit_path.expanduser()

    if DEFAULT_ORIGINAL_ASAR_PATH.is_file():
        return DEFAULT_ORIGINAL_ASAR_PATH

    return DEFAULT_ASAR_PATH


def target_path_for_asset(asset: ThemeAsset) -> Path:
    return PANDANET_CUSTOM_ASSET_DIR / asset.filename


def css_ref_for_asset(asset: ThemeAsset) -> str:
    return f"../img/custom/{asset.filename}"


def js_ref_for_asset(asset: ThemeAsset) -> str:
    return f"img/custom/{asset.filename}"
