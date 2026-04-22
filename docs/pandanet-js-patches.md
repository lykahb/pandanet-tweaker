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
- Current seam: `function K4(a,b)`
- Search anchor:
  - `function K4(a,b)`
  - `J4(a,"grid-canvas",c)`
  - `J4(a,"goban-canvas",b)`
- Current change:
  - stock: `J4(a,"goban-canvas",b)`
  - patched: `J4(a,"goban-canvas",c)`
- Why this seam:
  - `K4(...)` is the canvas creation function.
  - It is the narrowest place where the goban canvas size can be changed without touching grid math.
- Failure symptom:
  - themed stones on the first and last lines are clipped
- Tests:
  - `test_patch_js_expand_goban_canvas_replaces_inset_layout`

### `expand_goban_canvas_position`

- Purpose: keep the enlarged goban canvas aligned with the full board bounds.
- File: `app/js/gopanda.js`
- Current seam: `function N4(a,b)`
- Search anchor:
  - `["goban-canvas",a]`
  - `Ky,ou.j(b),Qz,ou.j(b)`
- Current change:
  - stock: `new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null)`
  - patched: `new l(null,2,[Ky,0,Qz,0],null)`
- Why this seam:
  - `N4(...)` applies the DOM layout for the already-created canvases.
  - The matcher is regex-based because this block may be wrapped across lines in minified output.
- Failure symptom:
  - the patch fails with “Could not find goban canvas positioning block”
  - or goban-canvas remains inset while using the larger size
- Tests:
  - `test_patch_js_expand_goban_canvas_replaces_inset_layout`
  - `test_patch_js_expand_goban_canvas_handles_wrapped_positioning_block`

### `translate_expanded_goban_context`

- Purpose: preserve Pandanet's original goban inset as a drawing-space translation after the goban canvas is expanded.
- File: `app/js/gopanda.js`
- Current seam: `function q0(a,b,c,d)`
- Search anchor:
  - `function q0(a,b,c,d)`
  - `jk([Xr,jx,Qia,yca,QA,R,Qx,voa,Uy,rH]`
  - `e.getContext("2d")`
- Current change:
  - stock stores `e.getContext("2d")` directly under `Uy`
  - patched stores `window.__pandanetTweakerInstallGobanContext(e.getContext("2d"),d)` under `Uy`
- Why this seam:
  - `q0(...)` builds the goban render state.
  - `Uy` is the goban 2D context used by stones, preview stones, review marks, labels, and the last-move marker path.
  - Fixing the context here is more robust than patching individual canvas methods for every overlay type.
- Failure symptom:
  - review hover preview is offset
  - review marks, letters, or numbers are offset
  - stones and marks no longer share the same coordinate space
- Tests:
  - `test_patch_js_translate_expanded_goban_context_wraps_q0_goban_context`

### `force_review_full_redraw`

- Purpose: avoid review-mode repaint artifacts when runtime stone geometry overrides make stones extend beyond a single cell box.
- File: `app/js/gopanda.js`
- Current seam: `function V0(a,b)`
- Search anchor:
  - `function V0(a,b)`
  - `w0(a,b);return U0(a,c,b)`
  - `function W0(a)`
- Current change:
  - stock: `function V0(a,b){...w0(a,b);return U0(a,c,b)}`
  - patched: `function V0(a,b){return W0(a)}`
- Why this seam:
  - `V0(...)` is the review-mode incremental redraw helper.
  - `W0(...)` is Pandanet's own full-board redraw path.
- Failure symptom:
  - review mode leaves trails or partial redraw artifacts near changed intersections
- Tests:
  - `test_patch_js_force_full_board_redraw_replaces_incremental_redraw`

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

- Verify `q0(...)` still stores the goban 2D context under `Uy`.
- Verify `K4(...)` still creates `grid-canvas`, `shadow-canvas`, and `goban-canvas`.
- Verify `N4(...)` still positions `goban-canvas` using the `ou` inset.
- Verify `V0(...)` still represents single-cell review redraw and `W0(...)` still represents full-board redraw.

## Source Version

- Extracted reference archive: `GoPanda2.app/Contents/Resources/app.asar`
- Reference workspace path: `extracted-app/app/js/gopanda.js`
- Last updated: April 20, 2026
