# Pandanet JS Patches

This document records the minified `app/js/gopanda.js` seams that the tool patches.

The goal is not to explain the whole client. The goal is to make future upgrades faster when a new GoPanda release changes minified code and one of the patch matchers stops working.

## Upgrade Workflow

1. Extract the new `app.asar`.
2. Search `app/js/gopanda.js` for the patch anchors listed below.
3. Confirm that the same semantic seam still exists.
4. Update the exact snippet or regex in `src/pandanet_tweaker/pipeline.py`.
5. Re-run the focused unit tests that cover the patch.
6. Verify visually in the app:
   - observation mode stones
   - review hover preview
   - review marks and labels
   - last-move marker
   - edge stones on the first and last lines

## Patch Ledger

### `expand_goban_canvas_creation`

- Purpose: prevent enlarged or shifted stones from being clipped on the outer lines.
- File: `app/js/gopanda.js`
- Current seams:
  - macOS/Linux reference: `function K4(a,b)`
  - Windows reference: `function H4(a,b)`
- Search anchor:
  - `grid-canvas`
  - `shadow-canvas`
  - `goban-canvas`
- Current change:
  - macOS/Linux stock: `J4(a,"goban-canvas",b)`
  - macOS/Linux patched: `J4(a,"goban-canvas",c)`
  - Windows stock: `G4(a,"goban-canvas",b)`
  - Windows patched: `G4(a,"goban-canvas",c)`
- Why this seam:
  - This is the nested canvas creation function for `grid-canvas`, `shadow-canvas`, and `goban-canvas`.
  - It is the narrowest place where the goban canvas size can be changed without touching grid math.
- Failure symptom:
  - themed stones on the first and last lines are clipped
- Tests:
  - `test_patch_js_expand_goban_canvas_replaces_inset_layout`
  - `test_patch_js_expand_goban_canvas_replaces_windows_inset_layout`

### `expand_goban_canvas_position`

- Purpose: keep the enlarged goban canvas aligned with the full board bounds.
- File: `app/js/gopanda.js`
- Current seams:
  - macOS/Linux reference: `function N4(a,b)`
  - Windows reference: `function K4(a,b)`
- Search anchor:
  - `["goban-canvas",a]`
  - macOS/Linux inset tuple: `Ky,ou.j(b),Qz,ou.j(b)`
  - Windows inset tuple: `Ly,qu.fa(b),Rz,qu.fa(b)`
- Current change:
  - macOS/Linux stock: `new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null)`
  - macOS/Linux patched: `new l(null,2,[Ky,0,Qz,0],null)`
  - Windows stock: `new l(null,2,[Ly,qu.fa(b),Rz,qu.fa(b)],null)`
  - Windows patched: `new l(null,2,[Ly,0,Rz,0],null)`
- Why this seam:
  - This block applies the DOM layout for the already-created canvases.
  - The matcher is regex-based because this block may be wrapped across lines in minified output.
- Failure symptom:
  - the patch fails with “Could not find goban canvas positioning block”
  - or goban-canvas remains inset while using the larger size
- Tests:
  - `test_patch_js_expand_goban_canvas_replaces_inset_layout`
  - `test_patch_js_expand_goban_canvas_handles_wrapped_positioning_block`
  - `test_patch_js_expand_goban_canvas_replaces_windows_inset_layout`

### `translate_expanded_goban_context`

- Purpose: preserve Pandanet's original goban inset as a drawing-space translation after the goban canvas is expanded.
- File: `app/js/gopanda.js`
- Current seams:
  - macOS/Linux reference: `function q0(a,b,c,d)`
  - Windows reference: `function n0(a,b,c,d)`
- Search anchor:
  - `["goban-canvas",a]`
  - `["grid-canvas",a]`
  - `["shadow-canvas",a]`
  - `e.getContext("2d")`
- Current change:
  - stock stores `e.getContext("2d")` directly in the goban render-state map
  - patched stores `window.__pandanetTweakerInstallGobanContext(e.getContext("2d"),d)` there instead
- Why this seam:
  - This function builds the goban render state.
  - The stored goban 2D context is used by stones, preview stones, review marks, labels, and the last-move marker path.
  - Fixing the context here is more robust than patching individual canvas methods for every overlay type.
- Failure symptom:
  - review hover preview is offset
  - review marks, letters, or numbers are offset
  - stones and marks no longer share the same coordinate space
- Tests:
  - `test_patch_js_translate_expanded_goban_context_wraps_q0_goban_context`
  - `test_patch_js_translate_expanded_goban_context_wraps_windows_n0_goban_context`

### `force_review_full_redraw`

- Purpose: avoid review-mode repaint artifacts when runtime stone geometry overrides make stones extend beyond a single cell box.
- File: `app/js/gopanda.js`
- Current seams:
  - macOS/Linux reference: `function V0(a,b)`
  - Windows reference: `function V0(a,b,c)`
- Search anchor:
  - macOS/Linux tail: `w0(a,b);return U0(a,c,b)`
  - Windows tail: `return S0(a,c)}return null}`
- Current change:
  - macOS/Linux stock: `function V0(a,b){...w0(a,b);return U0(a,c,b)}`
  - macOS/Linux patched: `function V0(a,b){return W0(a)}`
  - Windows stock preserves the state update but ends with `return S0(a,c)`
  - Windows patched preserves the state update but ends with `return T0(a)`
- Why this seam:
  - `V0(...)` is the review-mode incremental redraw helper.
  - `W0(...)` and `T0(...)` are Pandanet's own full-board redraw paths in the current known builds.
- Failure symptom:
  - review mode leaves trails or partial redraw artifacts near changed intersections
- Tests:
  - `test_patch_js_force_full_board_redraw_replaces_incremental_redraw`
  - `test_patch_js_force_full_board_redraw_replaces_windows_incremental_redraw`

## Related Runtime Hooks

These are not minified-source replacements, but they rely on the seams above:

- `window.__pandanetTweakerInstallGobanContext(...)`
  - installed by the injected runtime script
  - applies the original inset translation to the goban context once
- `CanvasRenderingContext2D.prototype.drawImage`
  - used for custom stone transforms, random variants, and fuzzy placement
- `CanvasRenderingContext2D.prototype.arc`
  - used to keep the last-move marker aligned with the shifted stone center
- `CanvasRenderingContext2D.prototype.clearRect`
  - used to clear the full expanded goban canvas correctly during review redraws

## Runtime Checks

When a patch stops matching or a visual regression appears, these checks are useful:

- Verify the render-state builder still stores the goban 2D context directly from `goban-canvas.getContext("2d")`.
- Verify the canvas-creation seam still creates `grid-canvas`, `shadow-canvas`, and `goban-canvas` in one nested block.
- Verify the layout seam still positions `goban-canvas` using the inner inset rather than `0`.
- Verify `V0(...)` still represents single-cell review redraw and that `W0(...)` or `T0(...)` still provides full-board redraw in that build.

## Source Version

- Extracted reference archive: `GoPanda2.app/Contents/Resources/app.asar`
- Reference workspace path: `extracted-app/app/js/gopanda.js`
- Windows reference archive: `original-win-app.asar`
- Last updated: April 22, 2026
