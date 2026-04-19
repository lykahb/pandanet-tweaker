# Pandanet Theme Replacer

`pandanet-theme-replacer` is a single-purpose utility for swapping the board and stone theme inside the Pandanet desktop client by repacking its Electron `app.asar`.

The long-term target is the installed Pandanet bundle at:

`/Applications/GoPanda2.app/Contents/Resources/app.asar`

The project is built with Python and `uv`. Python handles asset loading, optional Sabaki theme import, planning, format conversion, CSS patching, and file replacement orchestration. ASAR extraction and packing are routed through Electron's maintained CLI via `asar` or `npm exec --package=@electron/asar asar --`.

## Scope

- Accept direct file inputs for:
  - background
  - black stone
  - white stone
- Optionally import a theme package, starting with Sabaki-compatible themes.
- Normalize those inputs into a small internal manifest with semantic roles:
  - `board`
  - `stone-black`
  - `stone-white`
- Map those roles onto Pandanet's actual asset files inside `app.asar`.
- Patch the client CSS so the goban board texture can either repeat or scale.
- Extract, replace, and repack a new `.asar`.

## Current State

This initialization pass sets up:

- A Python package and CLI entrypoint.
- Direct asset replacement from CLI parameters.
- Sabaki theme inspection for directories and `.zip` packages.
- A replacement planner and dry-run workflow.
- An ASAR adapter interface.
- A concrete Pandanet target map for the primary board and stone assets.
- CSS patching for goban board texture mode.
- Project documentation and the Pandanet asset inventory.

What is still intentionally unfinished:

- Image normalization is intentionally minimal for now:
  - background is converted to JPEG if needed
  - stones are converted to PNG if needed
- Size normalization is not implemented yet.
- Secondary Pandanet stone assets such as shadowed and variation images are documented but not generated from the imported theme yet.

## CLI

Inspect a theme:

```bash
uv run pandanet-theme-replacer inspect-theme /path/to/theme
```

Build a dry-run plan from direct asset files:

```bash
uv run pandanet-theme-replacer replace \
  --board-background /path/to/board.png \
  --board-background-mode scale \
  --black-stone /path/to/black.png \
  --white-stone /path/to/white.png \
  --dry-run
```

Use a Sabaki theme, but override just one asset:

```bash
uv run pandanet-theme-replacer replace /path/to/theme \
  --board-background /path/to/custom-board.jpg \
  --board-background-mode repeat \
  --dry-run
```

Repack to a new output file:

```bash
uv run pandanet-theme-replacer replace \
  --board-background /path/to/board.png \
  --board-background-mode scale \
  --black-stone /path/to/black.webp \
  --white-stone /path/to/white.jpg \
  --asar /Applications/GoPanda2.app/Contents/Resources/app.asar \
  --output ./build/pandanet-themed.asar
```

## Board Background Modes

- `repeat`: preserve Pandanet's tiling board background behavior.
- `scale`: patch `app/css/site.css` so the board background is rendered once and stretched to fill the goban area.

To avoid ambiguity:

- `--board-background` refers to the wood texture inside `.goban`.
- The area around the board is styled separately by `.goban-page`, which uses CSS radial gradients rather than an image.

## Current Conversion Rules

- The board asset is written to `app/img/wood-board.jpg`, so non-JPEG input is converted to JPEG.
- The black and white stone assets are written to `app/img/50/stone-black.png` and `app/img/50/stone-white.png`, so non-PNG input is converted to PNG.
- No resizing or cropping is performed yet.

Image conversion currently uses macOS `sips`, which matches the target environment for this utility.

## Repository Layout

- `README.md`: project description and usage.
- `docs/plan.md`: build plan and milestones.
- `docs/pandanet-assets.md`: Pandanet client asset inventory and target mapping notes.
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
- Pandanet app inventory:
  - Extracted from `/Applications/GoPanda2.app/Contents/Resources/app.asar` on April 18, 2026 with `npm exec --package=@electron/asar asar`.
