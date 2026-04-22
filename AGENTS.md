# AGENTS.md

## Project Goal

Build a narrow CLI utility that replaces Pandanet board and stone assets inside `app.asar`, with Sabaki themes as the primary input format.

## Working Rules

- Keep the utility single-purpose. Avoid turning it into a generic Electron patcher.
- Treat `docs/pandanet-assets.md` as the source of truth for Pandanet asset paths and dimensions.
- Keep Sabaki import logic isolated from Pandanet target mapping.
- Prefer dry-run visibility before destructive or repacking behavior.
- Do not silently overwrite the installed Pandanet `app.asar`. Default to producing a new output file.

## Near-Term Priorities

1. Inventory the actual Pandanet theme assets inside `app.asar`.
2. Encode those targets in `src/pandanet_tweaker/targets/pandanet.py`.
3. Add image normalization rules if Pandanet expects fixed sizes or sprite sheets.
4. Add fixture-based integration tests around extract/replace/pack flow.
