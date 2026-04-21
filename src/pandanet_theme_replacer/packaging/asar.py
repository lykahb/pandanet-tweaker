from __future__ import annotations

import io
from importlib import import_module
from pathlib import Path

from pandanet_theme_replacer.errors import ExternalToolError


def extract_asar(asar_path: Path, destination: Path) -> None:
    asar_module = _import_asar_module()
    destination.mkdir(parents=True, exist_ok=True)
    try:
        asar_module.extract_archive(asar_path, destination)
    except Exception as exc:  # pragma: no cover - defensive wrapper around third-party library
        raise ExternalToolError(f"Python ASAR extract failed for {asar_path}: {exc}") from exc


def pack_asar(source_directory: Path, output_path: Path) -> None:
    asar_module = _import_asar_module()
    try:
        asar_module.create_archive(source_directory, output_path)
    except Exception as exc:  # pragma: no cover - defensive wrapper around third-party library
        raise ExternalToolError(f"Python ASAR pack failed for {source_directory}: {exc}") from exc


def read_asar_file(asar_path: Path, path_in_archive: Path) -> bytes:
    asar_module = _import_asar_module()
    try:
        with asar_module.AsarArchive(asar_path, "r") as archive:
            return archive.read(path_in_archive)
    except Exception as exc:  # pragma: no cover - defensive wrapper around third-party library
        raise ExternalToolError(
            f"Python ASAR read failed for {asar_path}:{path_in_archive}: {exc}"
        ) from exc


def rebuild_asar(source_asar: Path, output_path: Path, replacements: dict[Path, bytes]) -> None:
    asar_module = _import_asar_module()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            asar_module.AsarArchive(source_asar, "r") as source_archive,
            asar_module.AsarArchive(output_path, "w") as output_archive,
        ):
            _manual_rebuild_asar_archive(output_archive, source_archive, replacements)
    except Exception as exc:  # pragma: no cover - defensive wrapper around third-party library
        raise ExternalToolError(
            f"Python ASAR direct rebuild failed for {source_asar} -> {output_path}: {exc}"
        ) from exc


def _import_asar_module():
    try:
        asar_module = import_module("asar")
    except ModuleNotFoundError as exc:
        raise ExternalToolError(
            "Python ASAR backend is not available. Install the 'asar' package."
        ) from exc
    _patch_asar_module(asar_module)
    return asar_module


def _patch_asar_module(asar_module) -> None:
    if getattr(asar_module, "_pandanet_theme_replacer_patched", False):
        return

    asar_impl = import_module("asar.asar")
    archive_class = asar_impl.AsarArchive
    limited_reader_class = import_module("asar.limited_reader").LimitedReader
    if getattr(archive_class, "_pandanet_theme_replacer_optional_integrity_patch", False):
        asar_module._pandanet_theme_replacer_patched = True
        return

    def _parse_metadata_with_optional_integrity(self, info, path_in):
        for name, child in info["files"].items():
            cur_path = path_in / name
            node = self._search_node_from_path(cur_path)
            if "files" in child:
                node.set_dir("unpacked" in child and bool(child["unpacked"]))
                self._parse_metadata(child, cur_path)
            elif "link" in child:
                node.set_link(Path(child["link"]))
            else:
                node.unpacked = "unpacked" in child and bool(child["unpacked"])
                node.type = asar_impl.Type.FILE
                node.integrity = child.get("integrity")
                node.size = child["size"]
                if node.unpacked:
                    node.file_path = self.asar_unpacked / node.path
                else:
                    node.offset = int(child["offset"])
                    node.file_reader = asar_impl.LimitedReader(
                        self._asar_io,
                        self._offset + node.offset,
                        node.size,
                    )

    archive_class._parse_metadata = _parse_metadata_with_optional_integrity
    archive_class._pandanet_theme_replacer_optional_integrity_patch = True

    if not getattr(limited_reader_class, "_pandanet_theme_replacer_seek_patch", False):

        def _seek_allow_end(self, offset, whence=io.SEEK_SET):
            end_offset = self._offset + self._size
            if whence == io.SEEK_SET:
                absolute_offset = self._offset + offset
            elif whence == io.SEEK_CUR:
                absolute_offset = self._reader.tell() + offset
            elif whence == io.SEEK_END:
                absolute_offset = end_offset + offset
            else:
                raise ValueError("invalid whence value")
            if not (self._offset <= absolute_offset <= end_offset):
                raise ValueError("seek position is out of bounds")
            self._remaining = end_offset - absolute_offset
            return self._reader.seek(absolute_offset, io.SEEK_SET)

        limited_reader_class.seek = _seek_allow_end
        limited_reader_class._pandanet_theme_replacer_seek_patch = True

    asar_module._pandanet_theme_replacer_patched = True


def _manual_rebuild_asar_archive(output_archive, source_archive, replacements: dict[Path, bytes]) -> None:
    pending = dict(replacements)

    for meta in source_archive.metas:
        meta_type = getattr(getattr(meta, "type", None), "name", "")
        if meta_type == "DIRECTORY":
            node = output_archive._search_node_from_path(meta.path)
            node.set_dir(getattr(meta, "unpacked", False))
            continue
        if meta_type == "LINK":
            node = output_archive._search_node_from_path(meta.path)
            node.set_link(meta.link)
            continue
        if meta_type != "FILE":
            continue

        data = pending.pop(meta.path, None)
        if data is None:
            data = source_archive.read(meta.path)
        stream = io.BytesIO(data)
        output_archive.pack_stream(meta.path, stream, should_unpack=getattr(meta, "unpacked", False))
        stream.seek(0)
        node = output_archive._search_node_from_path(meta.path)
        node.executable = getattr(meta, "executable", False)

    for path_in_archive, data in sorted(pending.items(), key=lambda item: item[0].as_posix()):
        stream = io.BytesIO(data)
        output_archive.pack_stream(path_in_archive, stream)
        stream.seek(0)

