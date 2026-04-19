# Build Plan

## Goal

Produce a small CLI that takes a Pandanet `app.asar`, accepts either direct asset files or a Sabaki-style theme, replaces the client board and stone assets, optionally patches goban board texture rendering, and writes a repacked `.asar`.

## Architecture

### 1. Input Layer

Responsibilities:

- Accept explicit CLI asset paths for board, black stone, and white stone.
- Accept a theme directory or `.zip`.
- Detect Sabaki package structure.
- Read theme metadata from `package.json`.
- Discover the image assets referenced by the theme CSS.
- Convert them into internal semantic roles: `board`, `stone-black`, `stone-white`.
- Allow direct asset arguments to override imported theme assets.

Status:

- Initialized.
- Direct asset path mode implemented.

### 2. Pandanet Target Layer

Responsibilities:

- Record the internal asset paths inside Pandanet's `app.asar`.
- Document expected sizes, alpha handling, and any sprite-sheet constraints.
- Maintain the mapping from semantic roles to Pandanet files.

Status:

- Primary paths identified.
- Base board and stone mapping encoded.
- Secondary derived stone assets still need generation rules.

### 3. Repacking Layer

Responsibilities:

- Extract `app.asar`.
- Replace the mapped files.
- Patch the CSS goban board texture mode between `repeat` and `scale`.
- Repack to a new `.asar`.
- Keep the implementation behind a small adapter so the tool can use `asar` or `npm exec --package=@electron/asar asar --`.

Status:

- Adapter initialized.
- Background mode patching implemented.

### 4. Verification

Responsibilities:

- Theme import unit tests.
- Replacement-plan tests.
- Later: fixture-based integration test for extract/replace/pack.

Status:

- Initial unit tests added.

## Next Implementation Steps

1. Add size normalization rules for the board and base stones.
2. Decide whether goban board texture `scale` should mean `100% 100%`, `contain`, or `cover`.
3. Generate or preserve secondary assets such as shadowed and variation stones.
4. Run a dry-run plan against a real Sabaki theme and a direct-asset workflow.
5. Run an end-to-end repack and validate the client visually.
