# Pandanet Theme Replacer

`pandanet-theme-replacer` is a single-purpose utility for swapping the board and stone theme inside the Pandanet desktop client by repacking its Electron `app.asar`.

The installed Pandanet bundle lives at:

`/Applications/GoPanda2.app/Contents/Resources/app.asar`

For repeatable theming, keep the clean upstream archive alongside it as:

`/Applications/GoPanda2.app/Contents/Resources/original-app.asar`

The project is built with Python and `uv`. Python handles asset loading, optional Sabaki theme import, planning, CSS and JS patching, and file replacement orchestration. ASAR extraction and packing are routed through Electron's maintained CLI via `asar` or `npm exec --package=@electron/asar asar --`.

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
- Copy those assets into the patched archive and redirect Pandanet's CSS/JS references to them.
- Patch the client CSS so the goban board texture can either repeat or scale.
- Optionally tint the goban grid canvas with a CSS filter derived from a target RGBA color.
- Extract, replace, and repack a new `.asar`.

## Current State

This initialization pass sets up:

- A Python package and CLI entrypoint.
- Direct asset replacement from CLI parameters.
- Sabaki theme inspection for directories and `.zip` packages.
- A replacement planner and dry-run workflow.
- An ASAR adapter interface.
- A concrete Pandanet patch map for the primary board and stone references.
- CSS patching for goban board texture mode.
- Grid color override via a goban-scoped CSS filter.
- Narrow Sabaki stone transform import for `.shudan-stone-image.shudan-sign_1` and `.shudan-stone-image.shudan-sign_-1`.
- Project documentation and the Pandanet asset inventory.

What is still intentionally unfinished:

- Secondary Pandanet stone assets such as shadowed and variation images still use the stock client files.
- Size normalization is not implemented.
- Grid color and other canvas-drawn styling are still hardcoded in `gopanda.js`.

## CLI

Inspect a theme:

```bash
uv run pandanet-theme-replacer inspect-theme /path/to/theme
```

Build a dry-run plan from direct asset files:

```bash
uv run pandanet-theme-replacer replace \
  --board-background /path/to/board.svg \
  --board-background-mode scale \
  --black-stone /path/to/black.svg \
  --white-stone /path/to/white.svg \
  --grid-rgba '#c58a3ccc' \
  --fuzzy-stone-placement 0.08 \
  --dry-run
```

Use a Sabaki theme, but override just one asset:

```bash
uv run pandanet-theme-replacer replace /path/to/theme \
  --board-background /path/to/custom-board.svg \
  --board-background-mode repeat \
  --dry-run
```

Repack to a new output file:

```bash
uv run pandanet-theme-replacer replace \
  --board-background /path/to/board.svg \
  --board-background-mode scale \
  --black-stone /path/to/black.svg \
  --white-stone /path/to/white.svg \
  --output ./build/app.asar
```

When `--asar` is omitted, the tool looks for `/Applications/GoPanda2.app/Contents/Resources/original-app.asar` first and falls back to `app.asar`.

If you plan to try multiple themes repeatedly, add a persistent extracted cache so the tool does not unpack the original archive on every run:

```bash
uv run pandanet-theme-replacer replace \
  /path/to/theme \
  --cache-asar-dir ~/.cache/pandanet-theme-replacer/gopanda \
  --output ./build/app.asar
```

This option is mainly for iterative theme testing, not a one-off replacement.

When `--cache-asar-dir` is set, the tool extracts the source ASAR into that directory once, stores backups of the files it patches under `__pandanet_theme_replacer/original/`, restores those files before each run, clears `app/img/custom/`, and then applies the new theme in place. That makes repeated theme swaps much faster than re-extracting the whole archive each time.

## Install Into App

By default, the tool writes the patched archive to `build/app.asar`, which is ready for Finder replacement.

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

## Board Background Modes

- `repeat`: preserve Pandanet's tiling board background behavior.
- `scale`: patch `app/css/site.css` so the board background is rendered once and stretched to fill the goban area.

To avoid ambiguity:

- `--board-background` refers to the wood texture inside `.goban`.
- The area around the board is styled separately by `.goban-page`, which uses CSS radial gradients rather than an image.

## Asset Handling

- The primary board and stone assets are copied into `app/img/custom/` with their original file extensions preserved.
- Sabaki random stone variants such as `.shudan-random_1`, `.shudan-random_2`, and similar rules are also copied into `app/img/custom/` when present.
- `app/css/site.css` is patched to point `.goban`, `.capture.*`, and `.mark.*` at those copied assets.
- `app/js/gopanda.js` is patched so the main canvas stones load from the copied black and white stone files.
- Sabaki imports are normalized to match Shudan's smaller default stone footprint. Shudan effectively draws stones at about `92%` of the point size, while Pandanet uses the full point size, so imported Sabaki stone transforms are scaled down before they are applied in Pandanet.
- When a Sabaki theme defines per-stone `width`, `height`, `top`, and `left` on `.shudan-stone-image.shudan-sign_1` or `.shudan-stone-image.shudan-sign_-1`, the tool normalizes those percentage values in Python, patches related CSS background sizing/positioning, and injects a small runtime script that applies the same numeric transform to canvas `drawImage()` calls for the custom stone files.
- When Sabaki random stone variants are present, the runtime script chooses a stable random variant per board stone draw location so the stones do not flicker on redraw.
- `--board-background-mode` only changes how `.goban` renders the board asset: `repeat` or scaled-to-fit.
- `--grid-rgba` appends a goban-scoped CSS override for `.goban > .grid-canvas`.
- `--fuzzy-stone-placement` adds Shudan-style jitter to board stones. The value is a fraction of the drawn stone diameter, from `0` to `0.5`.
- SVG is the preferred format when available because Electron renders it natively; no rasterization is done for the primary assets.
- The fuzzy placement pattern follows Shudan's eight-direction shift map and neighbor-conflict suppression from `Goban.js` and `helper.js`, but the offset magnitude is scaled by the CLI value instead of being fixed in CSS.

## Grid Override

`--grid-rgba` takes a hex color in `#RRGGBB`, `#RRGGBBAA`, `#RGB`, or `#RGBA` form and derives a CSS `filter` plus `opacity` override for the board grid canvas.

This is roundabout, but it is necessary because Pandanet draws the grid lines directly onto a transparent canvas in JS with a hardcoded black stroke. CSS cannot change the canvas `strokeStyle` after the grid has already been drawn, so the only CSS-only option is to tint the rendered canvas as a whole.

The override is scoped to `.goban > .grid-canvas` because the `grid-canvas` class is also used elsewhere in the client for non-goban views.

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
