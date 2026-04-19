from __future__ import annotations

from pathlib import Path

from pandanet_theme_replacer.models import AssetRole

DEFAULT_ASAR_PATH = Path("/Applications/GoPanda2.app/Contents/Resources/app.asar")
PANDANET_SITE_CSS_PATH = Path("app/css/site.css")

PANDANET_THEME_TARGETS: dict[AssetRole, Path] = {
    AssetRole.BOARD: Path("app/img/wood-board.jpg"),
    AssetRole.STONE_BLACK: Path("app/img/50/stone-black.png"),
    AssetRole.STONE_WHITE: Path("app/img/50/stone-white.png"),
}

PANDANET_TARGET_FORMATS: dict[AssetRole, str] = {
    AssetRole.BOARD: "jpeg",
    AssetRole.STONE_BLACK: "png",
    AssetRole.STONE_WHITE: "png",
}
