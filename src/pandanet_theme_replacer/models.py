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
class ImportedTheme:
    source: Path
    root: Path
    format_name: str
    name: str
    version: str | None
    assets: tuple[ThemeAsset, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    def first_asset_for_role(self, role: AssetRole) -> ThemeAsset | None:
        for asset in self.assets:
            if asset.role == role:
                return asset
        return None


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
