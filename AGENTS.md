# AGENTS.md

## Project Goal

Build a narrow CLI utility that replaces Pandanet board and stone assets inside `app.asar`, with Sabaki themes as the primary input format.

Target the most recent Pandanet desktop client first. When compatibility breaks, update the newest client version before older builds.

## Working Rules

- Keep the utility single-purpose. Avoid turning it into a generic Electron patcher.
- Treat `docs/pandanet-assets.md` as the source of truth for Pandanet asset paths and dimensions.
- Keep Sabaki import logic isolated from Pandanet target mapping.
- Prefer dry-run visibility before destructive or repacking behavior.
- Do not silently overwrite the installed Pandanet `app.asar`. Default to producing a new output file.
- Keep `ARCHITECTURE.md` as the top-level system map and dependency boundary reference.
- Keep fragile `gopanda.js` patch anchors documented in `docs/pandanet-js-patches.md`.

## Near-Term Priorities

1. Add image normalization rules if Pandanet expects fixed sizes, derived assets, or sprite sheets.
2. Decide how to handle stale custom files when the input archive is already patched, or keep the tool explicitly scoped to clean `original-app.asar` inputs.
3. Generate or patch secondary stone assets if stock shadowed or variation files remain visibly mismatched.
4. Add fixture-based integration tests around extract/replace/rebuild flow.
5. Keep platform usage docs current for macOS, Linux AppImage, and future Windows support.
