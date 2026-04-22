from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pandanet_theme_replacer.assets import (
    build_theme_from_input_spec,
    merge_theme_assets,
    normalize_theme_assets,
)
from pandanet_theme_replacer.errors import ConfigurationError, ThemeImportError
from pandanet_theme_replacer.importers.sabaki import load_sabaki_theme
from pandanet_theme_replacer.models import (
    AssetRole,
    AssetReferenceMap,
    BackgroundMode,
    EXPECTED_THEME_ROLES,
    ImportedTheme,
    PlannedReplacement,
    ReplaceRequest,
    ReplacementPlan,
    StoneTransform,
    ThemeInputSpec,
)
from pandanet_theme_replacer.packaging.asar import read_asar_file, rebuild_asar
from pandanet_theme_replacer.targets.pandanet import (
    PANDANET_GOBAN_GRID_SELECTOR,
    PANDANET_GOBAN_SHADOW_SELECTOR,
    PANDANET_CSS_REF_REPLACEMENTS,
    PANDANET_GOPANDA_JS_PATH,
    PANDANET_INDEX_HTML_PATH,
    PANDANET_JS_REF_REPLACEMENTS,
    PANDANET_SITE_CSS_PATH,
    PANDANET_THEME_RUNTIME_JS_PATH,
    PANDANET_THEME_RUNTIME_SCRIPT_SRC,
    css_ref_for_asset,
    grid_rgba_to_css_filter,
    js_ref_for_asset,
    target_path_for_asset,
)
from pandanet_theme_replacer.theme_sources import stage_theme_source

GOBAN_BLOCK_PATTERN = re.compile(r"(?P<prefix>\.goban\s*\{)(?P<body>.*?)(?P<suffix>\n\})", re.DOTALL)
CSS_BLOCK_TEMPLATE = r"(?P<prefix>{selector}\s*\{{)(?P<body>.*?)(?P<suffix>\n\s*\}})"
GRID_OVERRIDE_BLOCK_PATTERN = re.compile(
    r"\n/\* pandanet-theme-replacer grid override \*/\n\.goban > \.grid-canvas \{\n.*?\n\}\n?",
    re.DOTALL,
)
SHADOW_OVERRIDE_BLOCK_PATTERN = re.compile(
    r"\n/\* pandanet-theme-replacer shadow override \*/\n\.goban canvas\.shadow-canvas \{\n.*?\n\}\n?",
    re.DOTALL,
)
INDEX_HTML_RUNTIME_SCRIPT_PATTERN = re.compile(
    rf'<script src="{re.escape(PANDANET_THEME_RUNTIME_SCRIPT_SRC)}" type="text/javascript"></script>'
)
INDEX_HTML_GOPANDA_SCRIPT_PATTERN = re.compile(
    r'(?P<tag><script src="js/gopanda\.js" type="text/javascript"></script>)'
)
# Keep these minified patch anchors documented in docs/pandanet-js-patches.md.
GOPANDA_INCREMENTAL_REDRAW_SNIPPET = "function V0(a,b){var c=J(a);a=t(c,Rw);c=t(c,lB);w0(a,b);return U0(a,c,b)}"
GOPANDA_FULL_REDRAW_SNIPPET = "function V0(a,b){return W0(a)}"
GOPANDA_GOBAN_CANVAS_CREATION_SNIPPET = (
    'function K4(a,b){var c=J(b);b=t(c,lD);c=t(c,Cz);return new Sf(null,J4(a,"grid-canvas",c),'
    'new Sf(null,J4(a,"shadow-canvas",b),new Sf(null,J4(a,"goban-canvas",b),null,1,null),2,null),3,null)}'
)
GOPANDA_GOBAN_CANVAS_EXPANDED_CREATION_SNIPPET = (
    'function K4(a,b){var c=J(b);b=t(c,lD);c=t(c,Cz);return new Sf(null,J4(a,"grid-canvas",c),'
    'new Sf(null,J4(a,"shadow-canvas",b),new Sf(null,J4(a,"goban-canvas",c),null,1,null),2,null),3,null)}'
)
GOPANDA_GOBAN_CANVAS_POSITION_SNIPPET = (
    'OT(function(){var n=W(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),'
    'new l(null,2,[Ky,ou.j(b),Qz,ou.j(b)],null),F(["px"]));'
)
GOPANDA_GOBAN_CANVAS_EXPANDED_POSITION_SNIPPET = (
    'OT(function(){var n=W(F(["goban-canvas",a]));return Z.j?Z.j(n):Z.call(null,n)}(),'
    'new l(null,2,[Ky,0,Qz,0],null),F(["px"]));'
)
GOPANDA_GOBAN_CANVAS_POSITION_PATTERN = re.compile(
    r'OT\(function\(\)\{var n=\s*W\(F\(\["goban-canvas",a\]\)\);return Z\.j\?Z\.j\(n\):Z\.call\(null,n\)\}\(\),'
    r'new l\(null,2,\[Ky,ou\.j\(b\),Qz,ou\.j\(b\)\],null\),F\(\["px"\]\)\);'
)
GOPANDA_Q0_CONTEXT_SNIPPET = (
    'function q0(a,b,c,d){var e=function(){var k=W(F(["goban-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),'
    'f=function(){var k=W(F(["grid-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),'
    'g=function(){var k=W(F(["shadow-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}();'
    'return jk([Xr,jx,Qia,yca,QA,R,Qx,voa,Uy,rH],[f.getContext("2d"),c,g,e,g.getContext("2d"),a,d,f,e.getContext("2d"),b])}'
)
GOPANDA_Q0_CONTEXT_PATCHED_SNIPPET = (
    'function q0(a,b,c,d){var e=function(){var k=W(F(["goban-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),'
    'f=function(){var k=W(F(["grid-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}(),'
    'g=function(){var k=W(F(["shadow-canvas",a]));return Z.j?Z.j(k):Z.call(null,k)}();'
    'return jk([Xr,jx,Qia,yca,QA,R,Qx,voa,Uy,rH],[f.getContext("2d"),c,g,e,g.getContext("2d"),a,d,f,window.__pandanetThemeReplacerInstallGobanContext?window.__pandanetThemeReplacerInstallGobanContext(e.getContext("2d"),d):e.getContext("2d"),b])}'
)


def inspect_theme(theme_path: Path, theme_format: str = "auto") -> ImportedTheme:
    with stage_theme_source(theme_path) as prepared:
        return _load_theme(prepared, theme_format)


def build_replacement_plan(
    theme: ImportedTheme,
    *,
    background_mode: BackgroundMode | None = None,
    grid_rgba: str | None = None,
    stone_scale: float = 1.0,
    fuzzy_stone_placement: float = 0.0,
    disable_default_shadows: bool = True,
) -> ReplacementPlan:
    operations: list[PlannedReplacement] = []
    post_actions: list[str] = []

    for role in EXPECTED_THEME_ROLES:
        source_asset = theme.first_asset_for_role(role)
        target_path = target_path_for_asset(source_asset) if source_asset is not None else None

        if source_asset is None:
            operations.append(
                PlannedReplacement(
                    role=role,
                    source_asset=None,
                    target_relative_path=target_path,
                    status="missing-source",
                    reason="No matching asset was detected in the imported theme.",
                )
            )
            continue

        operations.append(
            PlannedReplacement(
                role=role,
                source_asset=source_asset,
                target_relative_path=target_path,
                status="ready",
                reason="Ready to replace.",
            )
        )

    if background_mode is not None:
        post_actions.append(f"Patch {PANDANET_SITE_CSS_PATH} to set board background mode to '{background_mode.value}'.")
    post_actions.append(f"Patch {PANDANET_SITE_CSS_PATH} and {PANDANET_GOPANDA_JS_PATH} to point at custom board and stone assets.")
    if disable_default_shadows:
        post_actions.append(
            f"Patch {PANDANET_SITE_CSS_PATH} to hide {PANDANET_GOBAN_SHADOW_SELECTOR}."
        )
    if theme.stone_transforms or theme.stone_variants or stone_scale != 1.0 or fuzzy_stone_placement > 0:
        post_actions.append(
            f"Inject {PANDANET_THEME_RUNTIME_JS_PATH} and patch {PANDANET_INDEX_HTML_PATH} to apply stone rendering overrides at runtime."
        )
    if theme.stone_transforms or stone_scale != 1.0 or fuzzy_stone_placement > 0:
        post_actions.append(
            f"Patch {PANDANET_GOPANDA_JS_PATH} so goban-canvas uses the full board bounds instead of the inset inner bounds."
        )
        post_actions.append(
            f"Patch {PANDANET_GOPANDA_JS_PATH} so the expanded goban context keeps Pandanet's original inset as a drawing translation."
        )
        post_actions.append(
            f"Patch {PANDANET_GOPANDA_JS_PATH} so review-mode cell redraws use full-board redraw instead."
        )
    if fuzzy_stone_placement > 0:
        post_actions.append(
            f"Apply Shudan-style fuzzy stone placement with maximum offset {fuzzy_stone_placement:g} stone diameters."
        )
    if stone_scale != 1.0:
        post_actions.append(f"Scale all stones by {stone_scale:g}x around their center.")
    if grid_rgba is not None:
        post_actions.append(f"Patch {PANDANET_SITE_CSS_PATH} to tint {PANDANET_GOBAN_GRID_SELECTOR} with {grid_rgba}.")

    return ReplacementPlan(theme=theme, operations=tuple(operations), post_actions=tuple(post_actions))


def replace_theme(request: ReplaceRequest) -> ReplacementPlan:
    theme = load_input_theme(request.input_spec)
    grid_filter = None
    if not 0.1 <= request.stone_scale <= 5:
        raise ConfigurationError("Invalid --stone-scale value: must be between 0.1 and 5.")
    if not 0 <= request.fuzzy_stone_placement <= 0.5:
        raise ConfigurationError("Invalid --fuzzy-stone-placement value: must be between 0 and 0.5.")
    if request.grid_rgba is not None:
        try:
            grid_filter = grid_rgba_to_css_filter(request.grid_rgba)
        except ValueError as exc:
            raise ConfigurationError(f"Invalid --grid-rgba value: {exc}") from exc

    plan = build_replacement_plan(
        theme,
        background_mode=request.background_mode,
        grid_rgba=request.grid_rgba,
        stone_scale=request.stone_scale,
        fuzzy_stone_placement=request.fuzzy_stone_placement,
        disable_default_shadows=request.disable_default_shadows,
    )

    if request.dry_run:
        return plan

    unresolved = [operation for operation in plan.operations if operation.status != "ready"]
    if unresolved:
        raise ConfigurationError(
            "Replacement plan is incomplete. Provide board, black stone, and white stone assets "
            "through a theme or explicit file arguments."
        )

    asar_path = request.asar_path.expanduser().resolve()
    output_path = request.output_path.expanduser().resolve()

    if not asar_path.is_file():
        raise ThemeImportError(f"ASAR file does not exist: {asar_path}")

    _apply_replacement_plan_direct(
        asar_path,
        plan,
        background_mode=request.background_mode,
        grid_filter=grid_filter,
        stone_scale=request.stone_scale,
        fuzzy_stone_placement=request.fuzzy_stone_placement,
        disable_default_shadows=request.disable_default_shadows,
        output_path=output_path,
    )

    return plan


def load_input_theme(input_spec: ThemeInputSpec) -> ImportedTheme:
    explicit_assets = None
    if input_spec.has_explicit_assets:
        explicit_assets = build_theme_from_input_spec(input_spec)

    if input_spec.theme_path is None:
        if explicit_assets is None:
            raise ThemeImportError(
                "No input theme or assets were provided. Supply a theme path or explicit asset arguments."
            )
        return normalize_theme_assets(explicit_assets)

    with stage_theme_source(input_spec.theme_path) as prepared:
        theme = _load_theme(prepared, input_spec.theme_format)

    if explicit_assets is not None:
        theme = merge_theme_assets(theme, explicit_assets)

    return normalize_theme_assets(theme)


def _load_theme(prepared, theme_format: str) -> ImportedTheme:
    if theme_format not in {"auto", "sabaki"}:
        raise ThemeImportError(f"Unsupported theme format: {theme_format}")

    return load_sabaki_theme(prepared)


def _apply_replacement_plan_direct(
    source_asar_path: Path,
    plan: ReplacementPlan,
    *,
    background_mode: BackgroundMode | None,
    grid_filter,
    stone_scale: float,
    fuzzy_stone_placement: float,
    disable_default_shadows: bool,
    output_path: Path,
) -> None:
    asset_refs = build_asset_reference_map(plan.theme)
    stone_variant_refs = build_stone_variant_reference_map(plan.theme)
    effective_stone_transforms = build_effective_stone_transforms(plan.theme.stone_transforms, stone_scale)
    needs_runtime = bool(effective_stone_transforms or stone_variant_refs or fuzzy_stone_placement > 0)

    replacements: dict[Path, bytes] = {}
    for operation in plan.operations:
        assert operation.source_asset is not None
        assert operation.target_relative_path is not None
        replacements[operation.target_relative_path] = operation.source_asset.data

    for variant_assets in plan.theme.stone_variants.values():
        for asset in variant_assets:
            replacements[target_path_for_asset(asset)] = asset.data

    with TemporaryDirectory(prefix="pandanet-asar-direct-") as temp_dir:
        temp_root = Path(temp_dir)
        site_css_path = _stage_asar_file_for_patch(source_asar_path, temp_root, PANDANET_SITE_CSS_PATH)
        gopanda_js_path = _stage_asar_file_for_patch(source_asar_path, temp_root, PANDANET_GOPANDA_JS_PATH)

        patch_css_asset_references(site_css_path, asset_refs)
        patch_js_asset_references(gopanda_js_path, asset_refs)
        if effective_stone_transforms or fuzzy_stone_placement > 0:
            patch_js_expand_goban_canvas(gopanda_js_path)
            patch_js_translate_expanded_goban_context(gopanda_js_path)
            patch_js_force_full_board_redraw(gopanda_js_path)
        patch_shadow_canvas_override(
            site_css_path,
            disable_default_shadows=disable_default_shadows,
        )
        patch_css_stone_transforms(site_css_path, effective_stone_transforms)
        if needs_runtime:
            runtime_js_path = temp_root / PANDANET_THEME_RUNTIME_JS_PATH
            write_runtime_stone_transform_script(
                runtime_js_path,
                effective_stone_transforms,
                asset_refs.js_refs,
                stone_variant_refs,
                fuzzy_stone_placement,
            )
            index_html_path = _stage_asar_file_for_patch(source_asar_path, temp_root, PANDANET_INDEX_HTML_PATH)
            patch_index_html_for_runtime_script(index_html_path)
            replacements[PANDANET_INDEX_HTML_PATH] = index_html_path.read_bytes()
            replacements[PANDANET_THEME_RUNTIME_JS_PATH] = runtime_js_path.read_bytes()
        if grid_filter is not None:
            patch_grid_color_override(site_css_path, grid_filter)
        if background_mode is not None:
            patch_background_mode(
                site_css_path,
                background_mode,
                asset_refs.board_css_ref,
            )

        replacements[PANDANET_SITE_CSS_PATH] = site_css_path.read_bytes()
        replacements[PANDANET_GOPANDA_JS_PATH] = gopanda_js_path.read_bytes()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rebuild_asar(source_asar_path, output_path, replacements)


def _stage_asar_file_for_patch(source_asar_path: Path, temp_root: Path, relative_path: Path) -> Path:
    staged_path = temp_root / relative_path
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(read_asar_file(source_asar_path, relative_path))
    return staged_path


def patch_background_mode(site_css_path: Path, mode: BackgroundMode, board_css_ref: str) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")
    match = GOBAN_BLOCK_PATTERN.search(css_text)
    if match is None:
        raise ConfigurationError(f"Could not find .goban CSS block in {site_css_path}")

    body = match.group("body")
    lines = body.splitlines()
    filtered_lines = [
        line for line in lines if "background-size:" not in line and "background-position:" not in line
    ]

    replacement_lines: list[str] = []
    replaced_background = False
    for line in filtered_lines:
        if "background: url(" in line:
            if mode == BackgroundMode.REPEAT:
                replacement_lines.append(f'  background: url("{board_css_ref}") repeat;')
            else:
                replacement_lines.append(f'  background: url("{board_css_ref}") no-repeat;')
                replacement_lines.append("  background-size: 100% 100%;")
                replacement_lines.append("  background-position: center;")
            replaced_background = True
        else:
            replacement_lines.append(line)

    if not replaced_background:
        raise ConfigurationError(f"Could not find board background declaration in {site_css_path}")

    new_block = f"{match.group('prefix')}{''.join(f'{line}\n' for line in replacement_lines)}{match.group('suffix')}"
    site_css_path.write_text(css_text[: match.start()] + new_block + css_text[match.end() :], encoding="utf-8")


def build_stone_variant_reference_map(theme: ImportedTheme) -> dict[AssetRole, tuple[str, ...]]:
    return {
        role: tuple(js_ref_for_asset(asset) for asset in assets)
        for role, assets in theme.stone_variants.items()
        if assets
    }


def build_asset_reference_map(theme: ImportedTheme) -> AssetReferenceMap:
    css_refs: dict[AssetRole, str] = {}
    js_refs: dict[AssetRole, str] = {}
    board_css_ref = ""

    for role in EXPECTED_THEME_ROLES:
        asset = theme.first_asset_for_role(role)
        if asset is None:
            continue

        css_ref = css_ref_for_asset(asset)
        js_ref = js_ref_for_asset(asset)
        css_refs[role] = css_ref
        js_refs[role] = js_ref
        if role == AssetRole.BOARD:
            board_css_ref = css_ref

    if not board_css_ref:
        raise ConfigurationError("Replacement plan did not include a board asset.")

    return AssetReferenceMap(
        board_css_ref=board_css_ref,
        css_refs=css_refs,
        js_refs=js_refs,
    )


def patch_css_asset_references(
    site_css_path: Path,
    asset_refs: AssetReferenceMap,
) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")

    for stock_ref, role in PANDANET_CSS_REF_REPLACEMENTS.items():
        replacement = asset_refs.css_ref_for(role)
        css_text = css_text.replace(stock_ref, replacement)

    site_css_path.write_text(css_text, encoding="utf-8")


def patch_css_stone_transforms(site_css_path: Path, stone_transforms: dict[AssetRole, StoneTransform]) -> None:
    if not stone_transforms:
        return
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")
    selector_map = {
        AssetRole.STONE_BLACK: (
            ".goban-page .lid .lid-captures .capture.white",
            ".goban-page .info-panel .info-panel-wrapper .name-rank .mark.black",
        ),
        AssetRole.STONE_WHITE: (
            ".goban-page .lid .lid-captures .capture.black",
            ".goban-page .info-panel .info-panel-wrapper .name-rank .mark.white",
        ),
    }
    for role, selectors in selector_map.items():
        transform = stone_transforms.get(role)
        if transform is None:
            continue
        for selector in selectors:
            css_text = _patch_css_block(
                css_text,
                selector,
                {
                    "background-size": f"{transform.width} {transform.height}",
                    "background-position": f"{transform.left} {transform.top}",
                },
            )

    site_css_path.write_text(css_text, encoding="utf-8")


def patch_index_html_for_runtime_script(index_html_path: Path) -> None:
    if not index_html_path.is_file():
        raise ConfigurationError(f"Expected HTML file was not found: {index_html_path}")

    html_text = index_html_path.read_text(encoding="utf-8")
    if INDEX_HTML_RUNTIME_SCRIPT_PATTERN.search(html_text):
        return

    patched, count = INDEX_HTML_GOPANDA_SCRIPT_PATTERN.subn(
        rf'\g<tag>{chr(10)}    <script src="{PANDANET_THEME_RUNTIME_SCRIPT_SRC}" type="text/javascript"></script>',
        html_text,
        count=1,
    )
    if count != 1:
        raise ConfigurationError(f"Could not find gopanda.js script tag in {index_html_path}")

    index_html_path.write_text(patched, encoding="utf-8")


def write_runtime_stone_transform_script(
    runtime_js_path: Path,
    stone_transforms: dict[AssetRole, StoneTransform],
    js_refs: dict[AssetRole, str],
    stone_variant_js_refs: dict[AssetRole, tuple[str, ...]],
    fuzzy_stone_placement: float,
) -> None:
    if not stone_transforms and not stone_variant_js_refs and fuzzy_stone_placement <= 0:
        return

    runtime_js_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_js_path.write_text(
        build_runtime_stone_transform_script(
            stone_transforms,
            js_refs,
            stone_variant_js_refs,
            fuzzy_stone_placement,
        ),
        encoding="utf-8",
    )


def patch_js_asset_references(
    gopanda_js_path: Path,
    asset_refs: AssetReferenceMap,
) -> None:
    if not gopanda_js_path.is_file():
        raise ConfigurationError(f"Expected JS file was not found: {gopanda_js_path}")

    js_text = gopanda_js_path.read_text(encoding="utf-8")

    for stock_ref, role in PANDANET_JS_REF_REPLACEMENTS.items():
        js_text = js_text.replace(stock_ref, asset_refs.js_ref_for(role))

    gopanda_js_path.write_text(js_text, encoding="utf-8")


def patch_js_force_full_board_redraw(gopanda_js_path: Path) -> None:
    # Upgrade notes for this seam live in docs/pandanet-js-patches.md.
    if not gopanda_js_path.is_file():
        raise ConfigurationError(f"Expected JS file was not found: {gopanda_js_path}")

    js_text = gopanda_js_path.read_text(encoding="utf-8")
    if GOPANDA_FULL_REDRAW_SNIPPET in js_text:
        return

    patched = js_text.replace(GOPANDA_INCREMENTAL_REDRAW_SNIPPET, GOPANDA_FULL_REDRAW_SNIPPET, 1)
    if patched == js_text:
        raise ConfigurationError(f"Could not find V0 incremental redraw function in {gopanda_js_path}")

    gopanda_js_path.write_text(patched, encoding="utf-8")


def patch_js_expand_goban_canvas(gopanda_js_path: Path) -> None:
    # Upgrade notes for this seam live in docs/pandanet-js-patches.md.
    if not gopanda_js_path.is_file():
        raise ConfigurationError(f"Expected JS file was not found: {gopanda_js_path}")

    js_text = gopanda_js_path.read_text(encoding="utf-8")
    if (
        GOPANDA_GOBAN_CANVAS_EXPANDED_CREATION_SNIPPET in js_text
        and GOPANDA_GOBAN_CANVAS_EXPANDED_POSITION_SNIPPET in js_text
    ):
        return

    patched = js_text.replace(
        GOPANDA_GOBAN_CANVAS_CREATION_SNIPPET,
        GOPANDA_GOBAN_CANVAS_EXPANDED_CREATION_SNIPPET,
        1,
    )
    if patched == js_text:
        raise ConfigurationError(f"Could not find goban canvas creation function in {gopanda_js_path}")

    updated, count = GOPANDA_GOBAN_CANVAS_POSITION_PATTERN.subn(
        GOPANDA_GOBAN_CANVAS_EXPANDED_POSITION_SNIPPET,
        patched,
        count=1,
    )
    if count != 1:
        raise ConfigurationError(f"Could not find goban canvas positioning block in {gopanda_js_path}")

    gopanda_js_path.write_text(updated, encoding="utf-8")


def patch_js_translate_expanded_goban_context(gopanda_js_path: Path) -> None:
    # Upgrade notes for this seam live in docs/pandanet-js-patches.md.
    if not gopanda_js_path.is_file():
        raise ConfigurationError(f"Expected JS file was not found: {gopanda_js_path}")

    js_text = gopanda_js_path.read_text(encoding="utf-8")
    if GOPANDA_Q0_CONTEXT_PATCHED_SNIPPET in js_text:
        return

    patched = js_text.replace(GOPANDA_Q0_CONTEXT_SNIPPET, GOPANDA_Q0_CONTEXT_PATCHED_SNIPPET, 1)
    if patched == js_text:
        raise ConfigurationError(f"Could not find q0 goban context function in {gopanda_js_path}")

    gopanda_js_path.write_text(patched, encoding="utf-8")


def patch_grid_color_override(site_css_path: Path, grid_filter) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")
    css_text = GRID_OVERRIDE_BLOCK_PATTERN.sub("\n", css_text)
    override_block = (
        "\n/* pandanet-theme-replacer grid override */\n"
        f"{PANDANET_GOBAN_GRID_SELECTOR} {{\n"
        f"  filter: {grid_filter.filter_css};\n"
        f"  opacity: {grid_filter.opacity_css};\n"
        "}\n"
    )
    site_css_path.write_text(css_text.rstrip() + override_block, encoding="utf-8")


def patch_shadow_canvas_override(site_css_path: Path, *, disable_default_shadows: bool) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    css_text = site_css_path.read_text(encoding="utf-8")
    css_text = SHADOW_OVERRIDE_BLOCK_PATTERN.sub("\n", css_text)
    if disable_default_shadows:
        override_block = (
            "\n/* pandanet-theme-replacer shadow override */\n"
            f"{PANDANET_GOBAN_SHADOW_SELECTOR} {{\n"
            "  display: none;\n"
            "}\n"
        )
        css_text = css_text.rstrip() + override_block

    site_css_path.write_text(css_text, encoding="utf-8")


def _patch_css_block(css_text: str, selector: str, declarations: dict[str, str]) -> str:
    pattern = re.compile(CSS_BLOCK_TEMPLATE.format(selector=re.escape(selector)), re.DOTALL)
    match = pattern.search(css_text)
    if match is None:
        raise ConfigurationError(f"Could not find CSS block for selector '{selector}'")

    body = match.group("body")
    lines = body.splitlines()
    filtered = [
        line
        for line in lines
        if not any(f"{name}:" in line for name in declarations)
    ]
    filtered.extend(f"  {name}: {value};" for name, value in declarations.items())
    new_block = f"{match.group('prefix')}{''.join(f'{line}\n' for line in filtered)}{match.group('suffix')}"
    return css_text[: match.start()] + new_block + css_text[match.end() :]


def build_runtime_stone_transform_script(
    stone_transforms: dict[AssetRole, StoneTransform],
    js_refs: dict[AssetRole, str],
    stone_variant_js_refs: dict[AssetRole, tuple[str, ...]],
    fuzzy_stone_placement: float,
) -> str:
    config_entries: list[str] = []
    role_config_entries: list[str] = []
    for role in (AssetRole.STONE_BLACK, AssetRole.STONE_WHITE):
        js_ref = js_refs.get(role)
        if js_ref is None:
            continue
        transform = _runtime_transform_for_role(stone_transforms, role)
        role_key = "black" if role == AssetRole.STONE_BLACK else "white"
        config_entries.append(
            "    "
            + _js_string_literal(js_ref)
            + ": { "
            + f"left: {_percent_number(transform.left)}, "
            + f"top: {_percent_number(transform.top)}, "
            + f"width: {_percent_number(transform.width)}, "
            + f"height: {_percent_number(transform.height)}, "
            + "variants: ["
            + ", ".join(_js_string_literal(ref) for ref in stone_variant_js_refs.get(role, ()))
            + "] }"
        )
        role_config_entries.append(
            "    "
            + role_key
            + ": { "
            + f"left: {_percent_number(transform.left)}, "
            + f"top: {_percent_number(transform.top)}, "
            + f"width: {_percent_number(transform.width)}, "
            + f"height: {_percent_number(transform.height)} }}"
        )

    configs_block = ",\n".join(config_entries)
    role_configs_block = ",\n".join(role_config_entries)
    return (
        "(function(){\n"
        "  var proto = CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;\n"
        "  if (!proto) return;\n"
        "  if (proto.__pandanetThemeReplacerDrawImagePatched) return;\n"
        "  var configs = {\n"
        f"{configs_block}\n"
        "  };\n"
        "  var stoneRoleConfigs = {\n"
        f"{role_configs_block}\n"
        "  };\n"
        "  var variantImages = {};\n"
        "  var chosenVariantIndexes = {};\n"
        "  var chosenShifts = {};\n"
        "  var markerStateKey = '__pandanetThemeReplacerPendingMarkerState';\n"
        "  var originalDrawImage = proto.drawImage;\n"
        "  var originalClearRect = proto.clearRect;\n"
        "  var originalArc = proto.arc;\n"
        f"  var fuzzyStonePlacement = {format(fuzzy_stone_placement, 'g')};\n"
        "  var diagonalScale = Math.SQRT1_2 || (1 / Math.sqrt(2));\n"
        "  window.__pandanetThemeReplacerInstallGobanContext = function(ctx, inset) {\n"
        "    if (!ctx) return ctx;\n"
        "    var targetInset = typeof inset === 'number' ? inset : 0;\n"
        "    var currentInset = typeof ctx.__pandanetThemeReplacerGobanInset === 'number' ? ctx.__pandanetThemeReplacerGobanInset : 0;\n"
        "    if (ctx.__pandanetThemeReplacerContextInstalled && Math.abs(currentInset - targetInset) < 0.01) return ctx;\n"
        "    if (typeof ctx.translate === 'function') {\n"
        "      ctx.translate(targetInset - currentInset, targetInset - currentInset);\n"
        "    }\n"
        "    ctx.__pandanetThemeReplacerGobanInset = targetInset;\n"
        "    ctx.__pandanetThemeReplacerContextInstalled = true;\n"
        "    if (ctx.canvas) ctx.canvas.__pandanetThemeReplacerGobanInset = targetInset;\n"
        "    return ctx;\n"
        "  };\n"
        "  function cljsEq(left, right) {\n"
        "    return typeof D !== 'undefined' && D && typeof D.l === 'function' ? D.l(left, right) : left === right;\n"
        "  }\n"
        "  function resolveConfig(image) {\n"
        "    if (!image) return null;\n"
        "    var src = typeof image.currentSrc === 'string' && image.currentSrc ? image.currentSrc : image.src;\n"
        "    if (typeof src !== 'string') return null;\n"
        "    for (var key in configs) {\n"
        "      if (Object.prototype.hasOwnProperty.call(configs, key) && src.indexOf(key) !== -1) return { key: key, config: configs[key] };\n"
        "    }\n"
        "    return null;\n"
        "  }\n"
        "  function isGobanCanvas(ctx) {\n"
        "    var canvas = ctx && ctx.canvas;\n"
        "    if (!canvas) return false;\n"
        "    var className = typeof canvas.className === 'string' ? canvas.className : (canvas.className && canvas.className.baseVal) || '';\n"
        "    var id = typeof canvas.id === 'string' ? canvas.id : '';\n"
        "    return className.indexOf('goban-canvas') !== -1 || id.indexOf('goban-canvas') !== -1;\n"
        "  }\n"
        "  function getInstalledGobanInset(ctx) {\n"
        "    if (!isGobanCanvas(ctx)) return 0;\n"
        "    if (ctx && typeof ctx.__pandanetThemeReplacerGobanInset === 'number') return ctx.__pandanetThemeReplacerGobanInset;\n"
        "    var canvas = ctx && ctx.canvas;\n"
        "    if (canvas && typeof canvas.__pandanetThemeReplacerGobanInset === 'number') return canvas.__pandanetThemeReplacerGobanInset;\n"
        "    return 0;\n"
        "  }\n"
        "  function isLikelyFullCanvasClear(ctx, x, y, w, h) {\n"
        "    var canvas = ctx && ctx.canvas;\n"
        "    if (!canvas) return false;\n"
        "    var canvasWidth = canvas && typeof canvas.width === 'number' ? canvas.width : 0;\n"
        "    var canvasHeight = canvas && typeof canvas.height === 'number' ? canvas.height : 0;\n"
        "    if (!(canvasWidth > 0 && canvasHeight > 0)) return false;\n"
        "    if (Math.abs(x) > 0.01 || Math.abs(y) > 0.01) return false;\n"
        "    return w >= canvasWidth * 0.9 && h >= canvasHeight * 0.9;\n"
        "  }\n"
        "  function getVariantImage(configKey, dx, dy, dw, dh) {\n"
        "    var config = configs[configKey];\n"
        "    if (!config || !config.variants || config.variants.length === 0) return null;\n"
        "    if (!variantImages[configKey]) {\n"
        "      variantImages[configKey] = config.variants.map(function(src) {\n"
        "        var image = new Image();\n"
        "        image.src = src;\n"
        "        return image;\n"
        "      });\n"
        "    }\n"
        "    var selectionKey = [configKey, dx, dy, dw, dh].join('|');\n"
        "    if (!Object.prototype.hasOwnProperty.call(chosenVariantIndexes, selectionKey)) {\n"
        "      chosenVariantIndexes[selectionKey] = Math.floor(Math.random() * config.variants.length);\n"
        "    }\n"
        "    var image = variantImages[configKey][chosenVariantIndexes[selectionKey]];\n"
        "    if (image && image.complete && ((image.naturalWidth || 0) > 0 || (image.width || 0) > 0)) return image;\n"
        "    return null;\n"
        "  }\n"
        "  function randomInt(maxInclusive) {\n"
        "    return Math.floor(Math.random() * (maxInclusive + 1));\n"
        "  }\n"
        "  function boardKeyFor(ctx, dw, dh) {\n"
        "    var canvas = ctx && ctx.canvas;\n"
        "    var canvasWidth = canvas && typeof canvas.width === 'number' ? canvas.width : 0;\n"
        "    var canvasHeight = canvas && typeof canvas.height === 'number' ? canvas.height : 0;\n"
        "    return [canvasWidth, canvasHeight, Math.round(dw * 1000), Math.round(dh * 1000)].join('|');\n"
        "  }\n"
        "  function cellKeyFor(boardKey, cellX, cellY) {\n"
        "    return boardKey + '|' + cellX + '|' + cellY;\n"
        "  }\n"
        "  function removeConflictingNeighborShifts(shiftMap, boardKey, cellX, cellY) {\n"
        "    var direction = shiftMap[cellKeyFor(boardKey, cellX, cellY)] || 0;\n"
        "    var data = [\n"
        "      [[1, 5, 8], [cellX - 1, cellY], [3, 7, 6]],\n"
        "      [[2, 5, 6], [cellX, cellY - 1], [4, 7, 8]],\n"
        "      [[3, 7, 6], [cellX + 1, cellY], [1, 5, 8]],\n"
        "      [[4, 7, 8], [cellX, cellY + 1], [2, 5, 6]]\n"
        "    ];\n"
        "    for (var i = 0; i < data.length; i++) {\n"
        "      var item = data[i];\n"
        "      var directions = item[0];\n"
        "      if (directions.indexOf(direction) === -1) continue;\n"
        "      var neighbor = item[1];\n"
        "      var removeShifts = item[2];\n"
        "      var neighborKey = cellKeyFor(boardKey, neighbor[0], neighbor[1]);\n"
        "      if (removeShifts.indexOf(shiftMap[neighborKey]) !== -1) {\n"
        "        shiftMap[neighborKey] = 0;\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  function getShiftForStone(ctx, dx, dy, dw, dh) {\n"
        "    if (!(fuzzyStonePlacement > 0)) return 0;\n"
        "    var cellX = Math.round(dx / dw);\n"
        "    var cellY = Math.round(dy / dh);\n"
        "    return getShiftForCell(ctx, cellX, cellY, dw, dh);\n"
        "  }\n"
        "  function getShiftForCell(ctx, cellX, cellY, dw, dh) {\n"
        "    if (!(fuzzyStonePlacement > 0)) return 0;\n"
        "    var boardKey = boardKeyFor(ctx, dw, dh);\n"
        "    var key = cellKeyFor(boardKey, cellX, cellY);\n"
        "    if (!Object.prototype.hasOwnProperty.call(chosenShifts, key)) {\n"
        "      chosenShifts[key] = randomInt(8);\n"
        "      removeConflictingNeighborShifts(chosenShifts, boardKey, cellX, cellY);\n"
        "    }\n"
        "    return chosenShifts[key] || 0;\n"
        "  }\n"
        "  function getFuzzyOffset(shift, drawWidth, drawHeight) {\n"
        "    if (!(fuzzyStonePlacement > 0) || !shift) return { x: 0, y: 0 };\n"
        "    var cardinalX = drawWidth * fuzzyStonePlacement;\n"
        "    var cardinalY = drawHeight * fuzzyStonePlacement;\n"
        "    var diagonalX = cardinalX * diagonalScale;\n"
        "    var diagonalY = cardinalY * diagonalScale;\n"
        "    switch (shift) {\n"
        "      case 1: return { x: -cardinalX, y: 0 };\n"
        "      case 2: return { x: 0, y: -cardinalY };\n"
        "      case 3: return { x: cardinalX, y: 0 };\n"
        "      case 4: return { x: 0, y: cardinalY };\n"
        "      case 5: return { x: -diagonalX, y: -diagonalY };\n"
        "      case 6: return { x: diagonalX, y: -diagonalY };\n"
        "      case 7: return { x: diagonalX, y: diagonalY };\n"
        "      case 8: return { x: -diagonalX, y: diagonalY };\n"
        "      default: return { x: 0, y: 0 };\n"
        "    }\n"
        "  }\n"
        "  function setPendingMarkerState(ctx, baseCenterX, baseCenterY, shiftedCenterX, shiftedCenterY, cellSize) {\n"
        "    if (!ctx) return;\n"
        "    ctx[markerStateKey] = {\n"
        "      centerX: baseCenterX,\n"
        "      centerY: baseCenterY,\n"
        "      offsetX: shiftedCenterX - baseCenterX,\n"
        "      offsetY: shiftedCenterY - baseCenterY,\n"
        "      cellSize: cellSize\n"
        "    };\n"
        "  }\n"
        "  function clearPendingMarkerState(ctx) {\n"
        "    if (!ctx) return;\n"
        "    delete ctx[markerStateKey];\n"
        "  }\n"
        "  function isLikelyMarkerArc(ctx, state, x, y, r) {\n"
        "    if (!state) return false;\n"
        "    var centerTolerance = Math.max(0.5, state.cellSize * 0.02);\n"
        "    if (Math.abs(x - state.centerX) > centerTolerance || Math.abs(y - state.centerY) > centerTolerance) return false;\n"
        "    if (!(r > state.cellSize * 0.2 && r < state.cellSize * 0.35)) return false;\n"
        "    var lineWidth = typeof ctx.lineWidth === 'number' ? ctx.lineWidth : 0;\n"
        "    return lineWidth >= state.cellSize * 0.04 && lineWidth <= state.cellSize * 0.12;\n"
        "  }\n"
        "  proto.drawImage = function(image, dx, dy, dw, dh) {\n"
        "    if (arguments.length === 5) {\n"
        "      var resolved = resolveConfig(image);\n"
        "      if (resolved) {\n"
        "        var config = resolved.config;\n"
        "        var imageToDraw = getVariantImage(resolved.key, dx, dy, dw, dh) || image;\n"
        "        var drawWidth = dw * config.width / 100;\n"
        "        var drawHeight = dh * config.height / 100;\n"
        "        var fuzzyOffset = getFuzzyOffset(getShiftForStone(this, dx, dy, dw, dh), drawWidth, drawHeight);\n"
        "        var finalDx = dx + (dw * config.left / 100) + fuzzyOffset.x;\n"
        "        var finalDy = dy + (dh * config.top / 100) + fuzzyOffset.y;\n"
        "        setPendingMarkerState(this, dx + dw / 2, dy + dh / 2, finalDx + drawWidth / 2, finalDy + drawHeight / 2, Math.min(dw, dh));\n"
        "        return originalDrawImage.call(\n"
        "          this,\n"
        "          imageToDraw,\n"
        "          finalDx,\n"
        "          finalDy,\n"
        "          drawWidth,\n"
        "          drawHeight\n"
        "        );\n"
        "      }\n"
        "    }\n"
        "    clearPendingMarkerState(this);\n"
        "    return originalDrawImage.apply(this, arguments);\n"
        "  };\n"
        "  proto.clearRect = function(x, y, w, h) {\n"
        "    if (arguments.length === 4) {\n"
        "      if (isLikelyFullCanvasClear(this, x, y, w, h)) {\n"
        "        var canvas = this && this.canvas;\n"
        "        this.save();\n"
        "        if (typeof this.setTransform === 'function') this.setTransform(1, 0, 0, 1, 0, 0);\n"
        "        var result = originalClearRect.call(this, 0, 0, canvas.width, canvas.height);\n"
        "        this.restore();\n"
        "        return result;\n"
        "      }\n"
        "      return originalClearRect.call(this, x, y, w, h);\n"
        "    }\n"
        "    return originalClearRect.apply(this, arguments);\n"
        "  };\n"
        "  proto.arc = function(x, y, r, startAngle, endAngle, counterclockwise) {\n"
        "    var state = this && this[markerStateKey];\n"
        "    if (isLikelyMarkerArc(this, state, x, y, r)) {\n"
        "      x += state.offsetX;\n"
        "      y += state.offsetY;\n"
        "      clearPendingMarkerState(this);\n"
        "    }\n"
        "    return originalArc.call(this, x, y, r, startAngle, endAngle, counterclockwise);\n"
        "  };\n"
        "  proto.__pandanetThemeReplacerDrawImagePatched = true;\n"
        "}());\n"
    )


def _runtime_transform_for_role(
    stone_transforms: dict[AssetRole, StoneTransform],
    role: AssetRole,
) -> StoneTransform:
    return stone_transforms.get(role, StoneTransform(width="100%", height="100%", top="0%", left="0%"))


def build_effective_stone_transforms(
    stone_transforms: dict[AssetRole, StoneTransform],
    stone_scale: float,
) -> dict[AssetRole, StoneTransform]:
    effective: dict[AssetRole, StoneTransform] = {}
    for role in (AssetRole.STONE_BLACK, AssetRole.STONE_WHITE):
        transform = stone_transforms.get(role)
        if transform is None and stone_scale == 1.0:
            continue
        base_transform = transform or StoneTransform(width="100%", height="100%", top="0%", left="0%")
        effective[role] = scale_stone_transform(base_transform, stone_scale)
    return effective


def scale_stone_transform(transform: StoneTransform, stone_scale: float) -> StoneTransform:
    if stone_scale == 1.0:
        return transform

    width = _percent_value(transform.width)
    height = _percent_value(transform.height)
    left = _percent_value(transform.left)
    top = _percent_value(transform.top)
    new_width = width * stone_scale
    new_height = height * stone_scale
    left -= (new_width - width) / 2
    top -= (new_height - height) / 2
    return StoneTransform(
        width=f"{format(new_width, 'g')}%",
        height=f"{format(new_height, 'g')}%",
        top=f"{format(top, 'g')}%",
        left=f"{format(left, 'g')}%",
    )


def _js_string_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _percent_number(value: str) -> str:
    return format(float(value.removesuffix("%")), "g")


def _percent_value(value: str) -> float:
    return float(value.removesuffix("%"))
