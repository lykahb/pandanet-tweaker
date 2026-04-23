from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
import zipfile

from pandanet_tweaker.errors import ThemeImportError
from pandanet_tweaker.packaging.asar import extract_asar


@dataclass(frozen=True)
class PreparedThemeSource:
    source_path: Path
    staged_root: Path


@contextmanager
def stage_theme_source(source_path: Path) -> Iterator[PreparedThemeSource]:
    source_path = source_path.expanduser().resolve()

    if not source_path.exists():
        raise ThemeImportError(f"Theme source does not exist: {source_path}")

    if source_path.is_dir():
        yield PreparedThemeSource(source_path=source_path, staged_root=source_path)
        return

    suffix = source_path.suffix.lower()
    if suffix not in {".zip", ".asar"}:
        raise ThemeImportError(
            f"Unsupported theme source: {source_path}. Expected a directory, .zip file, or .asar file."
        )

    with TemporaryDirectory(prefix="pandanet-theme-") as temp_dir:
        temp_path = Path(temp_dir).resolve()
        if suffix == ".zip":
            with zipfile.ZipFile(source_path) as archive:
                archive.extractall(temp_path)
        else:
            extract_asar(source_path, temp_path)
        yield PreparedThemeSource(source_path=source_path, staged_root=temp_path)
