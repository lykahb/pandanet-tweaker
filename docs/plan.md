# Build Plan

## Goal

Produce a small CLI that takes a Pandanet `app.asar`, accepts either direct asset files or a Sabaki-style theme, copies the selected board and stone assets into the archive, patches Pandanet's CSS/JS references to them, optionally patches goban board texture rendering, and writes a repacked `.asar`.

The tool should default to reading from a preserved `original-app.asar` when available so rebuilt themes always start from a clean base.

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
- Extract narrow stone placement metadata from Sabaki CSS when it is expressed through `.shudan-stone-image.shudan-sign_1` and `.shudan-stone-image.shudan-sign_-1`.
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

- Extract `app.asar`.
- Optionally reuse a persistent extracted cache directory for repeated theme swaps and restore only the files mutated by the tool between runs.
- Copy custom board and stone assets into `app/img/custom/`.
- Patch stock CSS and JS references to point at those copied assets.
- Patch related CSS sizing/positioning and inject a small runtime script for canvas stone drawing when Sabaki themes specify stone scale and offset in CSS.
- Optionally append a goban-scoped CSS filter rule to tint the grid canvas.
- Patch the CSS goban board texture mode between `repeat` and `scale`.
- Repack to a new `.asar`.
- Keep the implementation behind a small adapter so the tool can use `asar` or `npm exec --package=@electron/asar asar --`.

Status:

- Adapter initialized.
- Background mode and asset-reference patching implemented.

### 4. Verification

Responsibilities:

- Theme import unit tests.
- Replacement-plan tests.
- Later: fixture-based integration test for extract/replace/pack.

Status:

- Initial unit tests added.

## Next Implementation Steps

1. Decide whether goban board texture `scale` should mean `100% 100%`, `contain`, or `cover`.
2. Decide whether `.capture.*` should keep using stock `-w-shadow` assets or switch to the custom stones permanently.
3. Generate or patch secondary assets such as shadowed and variation stones if the stock files remain visibly mismatched.
4. Run a dry-run plan against a real Sabaki theme and a direct-asset workflow.
5. Run an end-to-end repack and validate the client visually.
