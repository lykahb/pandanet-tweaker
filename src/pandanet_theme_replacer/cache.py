from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

from pandanet_theme_replacer.errors import ConfigurationError
from pandanet_theme_replacer.packaging.asar import extract_asar
from pandanet_theme_replacer.targets.pandanet import (
    PANDANET_CUSTOM_ASSET_DIR,
    PANDANET_GOPANDA_JS_PATH,
    PANDANET_INDEX_HTML_PATH,
    PANDANET_SITE_CSS_PATH,
    PANDANET_THEME_RUNTIME_JS_PATH,
)

CACHE_NAMESPACE_DIR = Path("__pandanet_theme_replacer")
CACHE_ORIGINAL_DIR = CACHE_NAMESPACE_DIR / "original"
CACHE_METADATA_PATH = CACHE_NAMESPACE_DIR / "cache.json"
CACHE_SENTINEL_PATH = CACHE_NAMESPACE_DIR / "managed"
CACHE_RESTORE_PATHS = (
    PANDANET_SITE_CSS_PATH,
    PANDANET_GOPANDA_JS_PATH,
    PANDANET_INDEX_HTML_PATH,
    PANDANET_THEME_RUNTIME_JS_PATH,
)


@dataclass(frozen=True)
class AsarCacheMetadata:
    source_path: str
    source_size: int
    source_mtime_ns: int

    def to_json(self) -> dict[str, int | str]:
        return {
            "source_path": self.source_path,
            "source_size": self.source_size,
            "source_mtime_ns": self.source_mtime_ns,
        }


def prepare_cached_asar_dir(cache_dir: Path, asar_path: Path) -> Path:
    cache_dir = cache_dir.expanduser().resolve()
    asar_path = asar_path.expanduser().resolve()
    expected = fingerprint_asar(asar_path)

    if _is_cache_current(cache_dir, expected):
        return cache_dir

    _initialize_cache_dir(cache_dir, asar_path, expected)
    return cache_dir


def restore_cached_asar_dir(cache_dir: Path) -> Path:
    cache_dir = cache_dir.expanduser().resolve()
    if not _is_managed_cache_dir(cache_dir):
        raise ConfigurationError(f"Cache directory is not initialized: {cache_dir}")

    for relative_path in CACHE_RESTORE_PATHS:
        destination = cache_dir / relative_path
        backup = cache_dir / CACHE_ORIGINAL_DIR / relative_path
        if backup.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, destination)
        elif destination.exists():
            destination.unlink()

    custom_asset_dir = cache_dir / PANDANET_CUSTOM_ASSET_DIR
    if custom_asset_dir.exists():
        shutil.rmtree(custom_asset_dir)
    custom_asset_dir.mkdir(parents=True, exist_ok=True)

    return cache_dir


def fingerprint_asar(asar_path: Path) -> AsarCacheMetadata:
    stat = asar_path.stat()
    return AsarCacheMetadata(
        source_path=str(asar_path),
        source_size=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
    )


def _initialize_cache_dir(cache_dir: Path, asar_path: Path, metadata: AsarCacheMetadata) -> None:
    if cache_dir.exists():
        if cache_dir.is_file():
            raise ConfigurationError(f"Cache path is a file, expected a directory: {cache_dir}")
        if any(cache_dir.iterdir()) and not _is_managed_cache_dir(cache_dir):
            raise ConfigurationError(
                f"Cache directory is not empty and is not managed by pandanet-theme-replacer: {cache_dir}"
            )
        _clear_directory(cache_dir)
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)

    extract_asar(asar_path, cache_dir)

    backup_root = cache_dir / CACHE_ORIGINAL_DIR
    backup_root.mkdir(parents=True, exist_ok=True)
    for relative_path in CACHE_RESTORE_PATHS:
        source = cache_dir / relative_path
        if not source.is_file():
            continue
        backup = backup_root / relative_path
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)

    custom_asset_dir = cache_dir / PANDANET_CUSTOM_ASSET_DIR
    if custom_asset_dir.exists():
        shutil.rmtree(custom_asset_dir)
    custom_asset_dir.mkdir(parents=True, exist_ok=True)

    (cache_dir / CACHE_SENTINEL_PATH).write_text("managed\n", encoding="utf-8")
    _write_metadata(cache_dir, metadata)


def _is_cache_current(cache_dir: Path, expected: AsarCacheMetadata) -> bool:
    if not _is_managed_cache_dir(cache_dir):
        return False

    try:
        current = _read_metadata(cache_dir)
    except (ConfigurationError, json.JSONDecodeError):
        return False

    return current == expected


def _is_managed_cache_dir(cache_dir: Path) -> bool:
    return cache_dir.is_dir() and (cache_dir / CACHE_SENTINEL_PATH).is_file()


def _clear_directory(path: Path) -> None:
    for entry in path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _read_metadata(cache_dir: Path) -> AsarCacheMetadata:
    metadata_path = cache_dir / CACHE_METADATA_PATH
    if not metadata_path.is_file():
        raise ConfigurationError(f"Cache metadata file was not found: {metadata_path}")

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    return AsarCacheMetadata(
        source_path=str(payload["source_path"]),
        source_size=int(payload["source_size"]),
        source_mtime_ns=int(payload["source_mtime_ns"]),
    )


def _write_metadata(cache_dir: Path, metadata: AsarCacheMetadata) -> None:
    metadata_path = cache_dir / CACHE_METADATA_PATH
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
