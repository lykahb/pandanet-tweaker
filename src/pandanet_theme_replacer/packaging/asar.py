from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from pandanet_theme_replacer.errors import ExternalToolError


def extract_asar(asar_path: Path, destination: Path) -> None:
    _run_asar_command("extract", asar_path, destination)


def pack_asar(source_directory: Path, output_path: Path) -> None:
    _run_asar_command("pack", source_directory, output_path)


def _run_asar_command(subcommand: str, left: Path, right: Path) -> None:
    command = _resolve_asar_command() + [subcommand, str(left), str(right)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "no output"
        raise ExternalToolError(f"ASAR command failed: {' '.join(command)}\n{detail}")


def _resolve_asar_command() -> list[str]:
    if shutil.which("asar"):
        return ["asar"]
    if shutil.which("npm"):
        return ["npm", "exec", "--package=@electron/asar", "asar", "--"]
    if shutil.which("npx"):
        return ["npx", "@electron/asar"]

    raise ExternalToolError(
        "No ASAR tool was found. Install 'asar' or ensure npm can execute '@electron/asar'."
    )
