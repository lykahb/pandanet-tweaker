from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pandanet_tweaker.packaging.asar import (
    extract_asar,
    pack_asar,
    read_asar_file,
    rebuild_asar,
)


class AsarPackagingTests(unittest.TestCase):
    def test_extract_asar_uses_python_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            asar_path = Path(temp_dir) / "app.asar"
            destination = Path(temp_dir) / "dst"
            asar_path.write_bytes(b"asar")

            calls: list[tuple[Path, Path]] = []

            class FakeAsarModule:
                @staticmethod
                def extract_archive(left: Path, right: Path) -> None:
                    calls.append((left, right))

            with patch("pandanet_tweaker.packaging.asar._import_asar_module", return_value=FakeAsarModule):
                extract_asar(asar_path, destination)
                self.assertTrue(destination.is_dir())

        self.assertEqual(calls, [(asar_path, destination)])

    def test_pack_asar_uses_python_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_directory = Path(temp_dir) / "src"
            output_path = Path(temp_dir) / "app.asar"
            source_directory.mkdir()

            calls: list[tuple[Path, Path]] = []

            class FakeAsarModule:
                @staticmethod
                def create_archive(left: Path, right: Path) -> None:
                    calls.append((left, right))

            with patch("pandanet_tweaker.packaging.asar._import_asar_module", return_value=FakeAsarModule):
                pack_asar(source_directory, output_path)

        self.assertEqual(calls, [(source_directory, output_path)])

    def test_read_asar_file_uses_python_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            asar_path = Path(temp_dir) / "app.asar"
            asar_path.write_bytes(b"asar")
            calls: list[tuple[Path, str, Path]] = []

            class FakeArchive:
                def __init__(self, archive_path: Path, mode: str) -> None:
                    self.archive_path = archive_path
                    self.mode = mode

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def read(self, path_in_archive: Path) -> bytes:
                    calls.append((self.archive_path, self.mode, path_in_archive))
                    return b"payload"

            class FakeAsarModule:
                AsarArchive = FakeArchive

            with patch("pandanet_tweaker.packaging.asar._import_asar_module", return_value=FakeAsarModule):
                result = read_asar_file(asar_path, Path("app/css/site.css"))

        self.assertEqual(result, b"payload")
        self.assertEqual(calls, [(asar_path, "r", Path("app/css/site.css"))])

    def test_rebuild_asar_uses_python_backend(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_asar = Path(temp_dir) / "original-app.asar"
            output_path = Path(temp_dir) / "build" / "app.asar"
            source_asar.write_bytes(b"asar")
            calls: list[tuple[str, object]] = []

            class FakeMetaType:
                def __init__(self, name: str) -> None:
                    self.name = name

            class FakeMeta:
                def __init__(self, path: str, type_name: str, unpacked: bool = False) -> None:
                    self.path = Path(path)
                    self.type = FakeMetaType(type_name)
                    self.unpacked = unpacked
                    self.link = Path("linked") if type_name == "LINK" else None
                    self.executable = False

            class FakeNode:
                def __init__(self) -> None:
                    self.executable = False

                def set_dir(self, unpacked: bool) -> None:
                    calls.append(("set_dir", unpacked))

                def set_link(self, link: Path) -> None:
                    calls.append(("set_link", link))

            class FakeSourceArchive:
                def __init__(self, archive_path: Path, mode: str) -> None:
                    self.archive_path = archive_path
                    self.mode = mode
                    self.metas = [
                        FakeMeta("app", "DIRECTORY"),
                        FakeMeta("app/main.js", "FILE"),
                    ]
                    calls.append(("open", (archive_path, mode)))

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def read(self, path_in_archive: Path) -> bytes:
                    calls.append(("read", path_in_archive))
                    return b"main"

            class FakeOutputArchive:
                def __init__(self, archive_path: Path, mode: str) -> None:
                    self.archive_path = archive_path
                    self.mode = mode
                    self.nodes: dict[Path, FakeNode] = {}
                    calls.append(("open", (archive_path, mode)))

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb) -> None:
                    return None

                def _search_node_from_path(self, path_in_archive: Path) -> FakeNode:
                    node = self.nodes.get(path_in_archive)
                    if node is None:
                        node = FakeNode()
                        self.nodes[path_in_archive] = node
                    calls.append(("node", path_in_archive))
                    return node

                def pack_stream(self, path_in_archive: Path, stream, should_unpack: bool = False) -> None:
                    calls.append(("pack_stream", (path_in_archive, stream.read(), should_unpack)))

            class FakeAsarModule:
                def AsarArchive(self, archive_path: Path, mode: str):
                    if mode == "r":
                        return FakeSourceArchive(archive_path, mode)
                    return FakeOutputArchive(archive_path, mode)

            with patch("pandanet_tweaker.packaging.asar._import_asar_module", return_value=FakeAsarModule()):
                rebuild_asar(
                    source_asar,
                    output_path,
                    {
                        Path("app/js/gopanda.js"): b"js",
                    },
                )
                self.assertTrue(output_path.parent.is_dir())

        self.assertIn(("read", Path("app/main.js")), calls)
        self.assertIn(("pack_stream", (Path("app/main.js"), b"main", False)), calls)
        self.assertIn(("pack_stream", (Path("app/js/gopanda.js"), b"js", False)), calls)


if __name__ == "__main__":
    unittest.main()
