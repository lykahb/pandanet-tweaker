from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class BackgroundMode(StrEnum):
    REPEAT = "repeat"
    SCALE = "scale"


class AssetRole(StrEnum):
    BOARD = "board"
    STONE_BLACK = "stone-black"
    STONE_WHITE = "stone-white"
    UNKNOWN = "unknown"


EXPECTED_THEME_ROLES = (
    AssetRole.BOARD,
    AssetRole.STONE_BLACK,
    AssetRole.STONE_WHITE,
)


@dataclass(frozen=True)
class ThemeAsset:
    role: AssetRole
    filename: str
    source_ref: str
    data: bytes
    notes: str | None = None

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class StoneTransform:
    width: str
    height: str
    top: str
    left: str


@dataclass(frozen=True)
class ThemeInputSpec:
    theme_path: Path | None = None
    theme_format: str = "auto"
    board_background_path: Path | None = None
    black_stone_path: Path | None = None
    white_stone_path: Path | None = None

    @property
    def explicit_asset_paths(self) -> tuple[Path, ...]:
        paths: list[Path] = []
        for path in (
            self.board_background_path,
            self.black_stone_path,
            self.white_stone_path,
        ):
            if path is not None:
                paths.append(path)
        return tuple(paths)

    @property
    def has_explicit_assets(self) -> bool:
        return bool(self.explicit_asset_paths)


@dataclass(frozen=True)
class ImportedTheme:
    source: Path
    root: Path
    format_name: str
    name: str
    version: str | None
    assets: tuple[ThemeAsset, ...]
    stone_transforms: dict[AssetRole, StoneTransform] = field(default_factory=dict)
    stone_variants: dict[AssetRole, tuple[ThemeAsset, ...]] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    def first_asset_for_role(self, role: AssetRole) -> ThemeAsset | None:
        preferred: ThemeAsset | None = None
        for asset in self.assets:
            if asset.role == role:
                if asset.notes == "css-role-match":
                    return asset
                if preferred is None or _asset_priority(role, asset) < _asset_priority(role, preferred):
                    preferred = asset
        return preferred


@dataclass(frozen=True)
class PlannedReplacement:
    role: AssetRole
    source_asset: ThemeAsset | None
    target_relative_path: Path | None
    status: str
    reason: str


@dataclass(frozen=True)
class ReplacementPlan:
    theme: ImportedTheme
    operations: tuple[PlannedReplacement, ...]
    post_actions: tuple[str, ...] = ()

    @property
    def unresolved_roles(self) -> tuple[AssetRole, ...]:
        unresolved: list[AssetRole] = []
        for operation in self.operations:
            if operation.status != "ready":
                unresolved.append(operation.role)
        return tuple(unresolved)


@dataclass(frozen=True)
class ReplaceRequest:
    input_spec: ThemeInputSpec
    asar_path: Path
    output_path: Path
    cache_asar_dir: Path | None = None
    background_mode: BackgroundMode | None = None
    grid_rgba: str | None = None
    fuzzy_stone_placement: float = 0.0
    disable_default_shadows: bool = True
    dry_run: bool = False


@dataclass(frozen=True)
class AssetReferenceMap:
    board_css_ref: str
    css_refs: dict[AssetRole, str]
    js_refs: dict[AssetRole, str]

    def css_ref_for(self, role: AssetRole) -> str:
        return self.board_css_ref if role == AssetRole.BOARD else self.css_refs[role]

    def js_ref_for(self, role: AssetRole) -> str:
        return self.js_refs[role]


def _asset_priority(role: AssetRole, asset: ThemeAsset) -> tuple[int, str]:
    name = asset.source_ref.lower()

    if role == AssetRole.BOARD:
        if any(token in name for token in ("board", "goban")):
            return (0, name)
        if any(token in name for token in ("background", "/bg", "_bg", "-bg", " bg")):
            return (2, name)
        return (1, name)

    return (0, name)
