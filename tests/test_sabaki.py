from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pandanet_theme_replacer.pipeline import inspect_theme


class SabakiImportTests(unittest.TestCase):
    def test_detects_board_and_stones_from_directory_theme(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text(
                '{"name": "example-theme", "version": "1.2.3"}',
                encoding="utf-8",
            )
            (root / "theme.css").write_text(
                """
                .board { background-image: url("board.jpg"); }
                .black { background-image: url("black.png"); }
                .white { background-image: url("white.png"); }
                """,
                encoding="utf-8",
            )
            (root / "board.jpg").write_bytes(b"board")
            (root / "black.png").write_bytes(b"black")
            (root / "white.png").write_bytes(b"white")

            theme = inspect_theme(root)

        self.assertEqual(theme.name, "example-theme")
        self.assertEqual({asset.role.value for asset in theme.assets}, {"board", "stone-black", "stone-white"})
        self.assertEqual(theme.warnings, ())


if __name__ == "__main__":
    unittest.main()
