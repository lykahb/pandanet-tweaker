# Build Plan

## Goal

Produce a small CLI that takes a Pandanet `app.asar`, accepts either direct asset files or a Sabaki-style theme, copies the selected board and stone assets into the archive, patches Pandanet's CSS/JS references to them, optionally patches goban board texture rendering, and writes a repacked `.asar`.

The tool should default to reading from a preserved `original-app.asar` when available so rebuilt themes always start from a clean base.

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

## Architecture

### 1. Input Layer

Responsibilities:

- Accept explicit CLI asset paths for board, black stone, and white stone.
- Accept a theme directory or `.zip`.
- Detect Sabaki package structure.
- Read theme metadata from `package.json`.
- Discover the image assets referenced by the theme CSS.
- Convert them into internal semantic roles: `board`, `stone-black`, `stone-white`.
- Preserve the original asset bytes and extensions so Electron can render SVG natively.
- Extract narrow stone placement metadata from Sabaki CSS when it is expressed through `.shudan-stone-image.shudan-sign_1` and `.shudan-stone-image.shudan-sign_-1`, then scale it down to compensate for Shudan's smaller default stone footprint before applying it in Pandanet.
- Allow direct asset arguments to override imported theme assets.

Status:

- Initialized.
- Direct asset path mode implemented.

### 2. Pandanet Target Layer

Responsibilities:

- Record the internal asset paths inside Pandanet's `app.asar`.
- Document expected sizes, alpha handling, and any sprite-sheet constraints for the stock client.
- Maintain the mapping from semantic roles to patched CSS/JS references and copied asset paths.

Status:

- Primary paths identified.
- Base board and stone mapping encoded.
- Secondary derived stone assets still need generation rules.

### 3. Repacking Layer

Responsibilities:

- Copy custom board and stone assets into `app/img/custom/`.
- Patch stock CSS and JS references to point at those copied assets.
- Patch related CSS sizing/positioning and inject a small runtime script for canvas stone drawing when Sabaki themes specify stone scale and offset in CSS.
- Expand Pandanet's inset `goban-canvas` to the full board bounds when runtime stone geometry overrides are active, then add the stock inset back only in the injected stone draw hook so outer stones are not clipped.
- Keep the last-move marker aligned with shifted stones by reusing the injected runtime script rather than patching hidden local functions in the minified Pandanet bundle.
- Optionally append a goban-scoped CSS filter rule to tint the grid canvas.
- Patch the CSS goban board texture mode between `repeat` and `scale`.
- Rebuild a new `.asar` directly from the source archive while overwriting only the patched files.

Status:

- Adapter initialized.
- Python ASAR rebuild path is the default replace flow.
- Background mode and asset-reference patching implemented.

### 4. Verification

Responsibilities:

- Theme import unit tests.
- Replacement-plan tests.
- Later: fixture-based integration test for extract/replace/pack.

Status:

- Initial unit tests added.

## Next Implementation Steps

1. Decide whether the direct rebuild path should grow a stale-file cleanup strategy for already patched source archives, or remain scoped to clean `original-app.asar` inputs.
2. Decide whether goban board texture `scale` should mean `100% 100%`, `contain`, or `cover`.
3. Decide whether `.capture.*` should keep using stock `-w-shadow` assets or switch to the custom stones permanently.
4. Generate or patch secondary assets such as shadowed and variation stones if the stock files remain visibly mismatched.
5. Run an end-to-end repack and validate the client visually.
