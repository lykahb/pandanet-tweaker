# Pandanet Tweaker

`pandanet-tweaker` lets you restyle the Pandanet desktop client with custom boards and stones.

It is built for people who want Pandanet to look more like the Go software they already enjoy, especially when they have a favorite Sabaki theme they want to carry over. Instead of manually digging through app files, the tool takes a theme or a few image files and builds a patched Pandanet app bundle for you.

The tool aims to support the most recent Pandanet desktop client version first. When the client changes, compatibility updates should target the newest release before older builds.

The project is built with Python and `uv`, but the product goal is simple: make Pandanet theming practical, repeatable, and reversible without turning the tool into a general-purpose app patcher.

Current implementation status lives in [docs/plan.md](/Users/borys/projects/pandanet-tweaker/docs/plan.md:1). Lower-level asset and rendering notes live in [docs/pandanet-assets.md](/Users/borys/projects/pandanet-tweaker/docs/pandanet-assets.md:1).

![Pandanet Tweaker screenshot with the BadukTV theme](docs/images/pandanet-baduktv.jpg)

*BadukTV theme, fuzzy stone placement. Generated with `uv run pandanet-tweaker replace --fuzzy-stone-placement=0.04 --stone-scale=0.97 ~/Downloads/Upsided-Sabaki-Themes-main/baduktv`.*


## Installation

If you are not used to Python tools, the setup is still straightforward. Install `uv`, download this project, open a terminal in the project folder, and run `uv sync` once.

You do not need to install Python separately first. `uv` can install the Python version the project needs automatically.

### 1. Install `uv`

On macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, open a new terminal window and check that `uv` works:

```bash
uv
```

If you prefer, `uv` is also available through package managers such as Homebrew on macOS and WinGet on Windows.

### 2. Download This Project

Download the project from GitHub as a ZIP file, then extract it somewhere easy to find, such as your Desktop or Downloads folder.

### 3. Open A Terminal In The Project Folder

Change into the project directory. For example:

```bash
cd ~/Downloads/pandanet-tweaker
```

### 4. Install The Project Dependencies

Run:

```bash
uv sync
```

This creates the local environment the tool uses and installs the required packages.

### 5. Run The Tool

Check that the command is available:

```bash
uv run pandanet-tweaker --help
```

The usual way to use the tool is `replace`.

For a first real run, use a Sabaki theme:

```bash
uv run pandanet-tweaker replace ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar
```

More common usage patterns are listed below.

## Usage

On macOS, the installed Pandanet bundle lives at:

`/Applications/GoPanda2.app/Contents/Resources/app.asar`

On Windows, the typical installed Pandanet archive lives at:

`C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources\app.asar`

To open that app directory in Finder, open `/Applications`, right-click `GoPanda2.app`, and choose `Show Package Contents`.

For repeatable theming on macOS, keep the clean upstream archive alongside it as:

`/Applications/GoPanda2.app/Contents/Resources/original-app.asar`

Most people will use `replace`.

Use a Sabaki theme:

```bash
uv run pandanet-tweaker replace ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar
```

Use plain image files:

```bash
uv run pandanet-tweaker replace \
  --board-background /path/to/board.svg \
  --black-stone /path/to/black.svg \
  --white-stone /path/to/white.svg
```

Use a Sabaki theme, but override one asset:

```bash
uv run pandanet-tweaker replace ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar \
  --board-background /path/to/custom-board.svg \
  --board-background-mode repeat
```

Write the patched result to a specific output file:

```bash
uv run pandanet-tweaker replace \
  --board-background /path/to/board.svg \
  --board-background-mode scale \
  --black-stone /path/to/black.svg \
  --white-stone /path/to/white.svg \
  --output ./build/app.asar
```

Preview the plan without writing a new archive yet:

```bash
uv run pandanet-tweaker replace ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar --dry-run
```

Advanced: inspect a theme without building a replacement:

```bash
uv run pandanet-tweaker inspect-theme ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar
```

Theme inputs can be a Sabaki theme `.asar` pack, a directory, or a `.zip`. The recommended input is a pack such as
`~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar`.

When `--asar` is omitted, the tool looks for the platform install `original-app.asar` first and falls back to `app.asar`.

- macOS default lookup: `/Applications/GoPanda2.app/Contents/Resources/original-app.asar`, then `app.asar`
- Windows default lookup: `C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources\original-app.asar`, then `app.asar`
- Linux: pass `--asar` explicitly to the `app.asar` inside the extracted AppImage tree

If you want to skip extracting the whole archive to the filesystem first, enable direct ASAR rebuild:

`replace` now always rebuilds the output ASAR directly from the source archive. It stages only the files the tool patches, overwrites those paths in a new archive, and leaves the installed Pandanet bundle untouched unless you replace the output yourself.

This flow is meant to start from a clean `original-app.asar` source. If you point it at an already patched archive, old extra files from earlier theme runs can remain in the output because the tool overwrites files but does not delete stale custom paths from the source archive.

## Install Into App

By default, the tool writes the patched archive to `build/app.asar`.

### macOS

On macOS, `build/app.asar` is ready for Finder replacement.

Before using the tool for the first time, preserve the original archive in Finder:

1. Quit GoPanda.
2. In Finder, open `/Applications`.
3. Right-click `GoPanda2.app` and choose `Show Package Contents`.
4. Open `Contents/Resources`.
5. Rename `app.asar` to `original-app.asar`.
6. Keep `original-app.asar` in that folder.

After generating `build/app.asar`, install the themed archive in Finder:

1. Open `/Applications/GoPanda2.app/Contents/Resources`.
2. Copy `build/app.asar` into that folder.
3. Replace the existing `app.asar`.

This keeps the clean base archive available, so the tool always rebuilds from the original app instead of stacking one theme patch on top of another.

Using Finder is the simplest path on macOS because terminal writes into app bundles under `/Applications` can be blocked by system privacy controls even when normal file permissions look correct.

### Linux

The Linux Pandanet client in this repository is distributed as `GoPanda2.AppImage`, which is a type-2 x86-64 AppImage with a built-in `--appimage-extract` mode. The practical Linux flow is: extract the AppImage, patch the extracted `app.asar`, then optionally rebuild a new AppImage.

Before using the tool for the first time on Linux:

1. Make the AppImage executable: `chmod +x GoPanda2.AppImage`
2. Extract it in place: `./GoPanda2.AppImage --appimage-extract`
3. Locate the Electron archive inside the extracted tree: `find squashfs-root -name app.asar`
4. Copy that archive to a preserved clean source next to it: `cp /path/to/app.asar /path/to/original-app.asar`

Build a patched archive from the extracted AppImage contents:

```bash
uv run pandanet-tweaker replace ~/Downloads/Upsided-Sabaki-Themes-main/packs/baduktv-grunge.asar \
  --asar /path/to/original-app.asar \
  --output /tmp/app.asar
```

Install the patched archive into the extracted AppImage tree:

1. Copy `/tmp/app.asar` over the extracted AppImage `app.asar` you found with `find`.
2. Keep `original-app.asar` alongside it so future runs always rebuild from the clean base archive.

At that point you have two Linux options:

1. Run the extracted application directly with `./squashfs-root/AppRun`
2. Rebuild a new AppImage from the modified extraction tree with `appimagetool squashfs-root GoPanda2-patched.AppImage`

The second step requires `appimagetool` on the Linux machine. This repository does not build AppImages itself; it only produces the patched `app.asar`.

### Windows

The typical Pandanet install path on Windows is:

`C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources\app.asar`

For repeatable theming, keep a clean upstream copy alongside it as:

`C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources\original-app.asar`

Before using the tool for the first time on Windows:

1. Quit GoPanda.
2. Open `C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources`.
3. Rename `app.asar` to `original-app.asar`.
4. Keep `original-app.asar` in that folder.

Build a patched archive:

```powershell
uv run pandanet-tweaker replace C:\Users\<username>\Downloads\Upsided-Sabaki-Themes-main\packs\baduktv-grunge.asar
```

Because the default lookup now includes the Windows install path, `--asar` is usually not needed when `original-app.asar` is already in `resources`.

After generating the patched archive, replace the installed archive in:

`C:\Users\<username>\AppData\Local\Programs\GoPanda2\resources\app.asar`

Keep `original-app.asar` in the same folder so future runs always rebuild from the clean stock client.

## Repository Layout

- `README.md`: project description and usage.
- `docs/plan.md`: build plan and milestones.
- `docs/pandanet-assets.md`: Pandanet client asset inventory and target mapping notes.
- `docs/pandanet-js-patches.md`: minified `gopanda.js` patch ledger for future app upgrades.
- `src/`: Python package and CLI.
- `tests/`: initial unit tests.
- `AGENTS.md`: project-specific guidance for future coding agents.

## Development

Run the test suite:

```bash
python3 -m unittest discover -s tests -t . -v
```

## Sources

- Sabaki theme examples: <https://github.com/billhails/SabakiThemes>
  - Repository README confirms themes are installed inside Sabaki as downloadable theme files.
  - The current importer makes a conservative inference from Sabaki package structure and CSS asset references.
- Python ASAR library: <https://pypi.org/project/asar/>
- Pandanet app inventory:
  - Extracted from `/Applications/GoPanda2.app/Contents/Resources/app.asar` on April 18, 2026.
