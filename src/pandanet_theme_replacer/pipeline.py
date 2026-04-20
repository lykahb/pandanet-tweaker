from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory

from pandanet_theme_replacer.assets import (
    build_theme_from_asset_files,
    merge_theme_assets,
    normalize_theme_assets,
)
from pandanet_theme_replacer.errors import ConfigurationError, ThemeImportError
from pandanet_theme_replacer.importers.sabaki import load_sabaki_theme
from pandanet_theme_replacer.models import (
    AssetRole,
    BackgroundMode,
    EXPECTED_THEME_ROLES,
    ImportedTheme,
    PlannedReplacement,
    ReplacementPlan,
    StoneTransform,
)
from pandanet_theme_replacer.packaging.asar import extract_asar, pack_asar
from pandanet_theme_replacer.targets.pandanet import (
    PANDANET_GOBAN_GRID_SELECTOR,
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
INDEX_HTML_RUNTIME_SCRIPT_PATTERN = re.compile(
    rf'<script src="{re.escape(PANDANET_THEME_RUNTIME_SCRIPT_SRC)}" type="text/javascript"></script>'
)
INDEX_HTML_GOPANDA_SCRIPT_PATTERN = re.compile(
    r'(?P<tag><script src="js/gopanda\.js" type="text/javascript"></script>)'
)


def inspect_theme(theme_path: Path, theme_format: str = "auto") -> ImportedTheme:
    with stage_theme_source(theme_path) as prepared:
        return _load_theme(prepared, theme_format)


def build_replacement_plan(
    theme: ImportedTheme,
    *,
    background_mode: BackgroundMode | None = None,
    grid_rgba: str | None = None,
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
    if theme.stone_transforms:
        post_actions.append(
            f"Inject {PANDANET_THEME_RUNTIME_JS_PATH} and patch {PANDANET_INDEX_HTML_PATH} to apply stone transforms at runtime."
        )
    if grid_rgba is not None:
        post_actions.append(f"Patch {PANDANET_SITE_CSS_PATH} to tint {PANDANET_GOBAN_GRID_SELECTOR} with {grid_rgba}.")

    return ReplacementPlan(theme=theme, operations=tuple(operations), post_actions=tuple(post_actions))


def replace_theme(
    theme_path: Path | None,
    asar_path: Path,
    output_path: Path,
    *,
    background_path: Path | None = None,
    black_stone_path: Path | None = None,
    white_stone_path: Path | None = None,
    background_mode: BackgroundMode | None = None,
    grid_rgba: str | None = None,
    dry_run: bool = False,
    theme_format: str = "auto",
) -> ReplacementPlan:
    theme = load_input_theme(
        theme_path,
        theme_format=theme_format,
        background_path=background_path,
        black_stone_path=black_stone_path,
        white_stone_path=white_stone_path,
    )
    grid_filter = None
    if grid_rgba is not None:
        try:
            grid_filter = grid_rgba_to_css_filter(grid_rgba)
        except ValueError as exc:
            raise ConfigurationError(f"Invalid --grid-rgba value: {exc}") from exc

    plan = build_replacement_plan(theme, background_mode=background_mode, grid_rgba=grid_rgba)

    if dry_run:
        return plan

    unresolved = [operation for operation in plan.operations if operation.status != "ready"]
    if unresolved:
        raise ConfigurationError(
            "Replacement plan is incomplete. Provide board, black stone, and white stone assets "
            "through a theme or explicit file arguments."
        )

    asar_path = asar_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    if not asar_path.is_file():
        raise ThemeImportError(f"ASAR file does not exist: {asar_path}")

    with TemporaryDirectory(prefix="pandanet-asar-") as temp_dir:
        temp_root = Path(temp_dir)
        extracted_dir = temp_root / "app"
        extract_asar(asar_path, extracted_dir)

        asset_refs = build_asset_reference_map(plan.theme)
        for operation in plan.operations:
            assert operation.source_asset is not None
            assert operation.target_relative_path is not None

            destination = extracted_dir / operation.target_relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(operation.source_asset.data)

        patch_css_asset_references(extracted_dir / PANDANET_SITE_CSS_PATH, asset_refs)
        patch_js_asset_references(extracted_dir / PANDANET_GOPANDA_JS_PATH, asset_refs)
        patch_css_stone_transforms(extracted_dir / PANDANET_SITE_CSS_PATH, plan.theme.stone_transforms)
        if plan.theme.stone_transforms:
            write_runtime_stone_transform_script(
                extracted_dir / PANDANET_THEME_RUNTIME_JS_PATH,
                plan.theme.stone_transforms,
                asset_refs[2],
            )
            patch_index_html_for_runtime_script(extracted_dir / PANDANET_INDEX_HTML_PATH)
        if grid_filter is not None:
            patch_grid_color_override(extracted_dir / PANDANET_SITE_CSS_PATH, grid_filter)
        if background_mode is not None:
            patch_background_mode(extracted_dir / PANDANET_SITE_CSS_PATH, background_mode, asset_refs[0])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pack_asar(extracted_dir, output_path)

    return plan


def load_input_theme(
    theme_path: Path | None,
    *,
    theme_format: str = "auto",
    background_path: Path | None = None,
    black_stone_path: Path | None = None,
    white_stone_path: Path | None = None,
) -> ImportedTheme:
    explicit_assets = None
    if any(path is not None for path in (background_path, black_stone_path, white_stone_path)):
        explicit_assets = build_theme_from_asset_files(
            background_path=background_path,
            black_stone_path=black_stone_path,
            white_stone_path=white_stone_path,
        )

    if theme_path is None:
        if explicit_assets is None:
            raise ThemeImportError(
                "No input theme or assets were provided. Supply a theme path or explicit asset arguments."
            )
        return normalize_theme_assets(explicit_assets)

    with stage_theme_source(theme_path) as prepared:
        theme = _load_theme(prepared, theme_format)

    if explicit_assets is not None:
        theme = merge_theme_assets(theme, explicit_assets)

    return normalize_theme_assets(theme)


def _load_theme(prepared, theme_format: str) -> ImportedTheme:
    if theme_format not in {"auto", "sabaki"}:
        raise ThemeImportError(f"Unsupported theme format: {theme_format}")

    return load_sabaki_theme(prepared)


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


def build_asset_reference_map(theme: ImportedTheme) -> tuple[str, dict[AssetRole, str], dict[AssetRole, str]]:
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

    return board_css_ref, css_refs, js_refs


def patch_css_asset_references(
    site_css_path: Path,
    asset_refs: tuple[str, dict[AssetRole, str], dict[AssetRole, str]],
) -> None:
    if not site_css_path.is_file():
        raise ConfigurationError(f"Expected CSS file was not found: {site_css_path}")

    board_css_ref, css_refs, _ = asset_refs
    css_text = site_css_path.read_text(encoding="utf-8")

    for stock_ref, role in PANDANET_CSS_REF_REPLACEMENTS.items():
        replacement = board_css_ref if role == AssetRole.BOARD else css_refs[role]
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
) -> None:
    if not stone_transforms:
        return

    runtime_js_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_js_path.write_text(build_runtime_stone_transform_script(stone_transforms, js_refs), encoding="utf-8")


def patch_js_asset_references(
    gopanda_js_path: Path,
    asset_refs: tuple[str, dict[AssetRole, str], dict[AssetRole, str]],
) -> None:
    if not gopanda_js_path.is_file():
        raise ConfigurationError(f"Expected JS file was not found: {gopanda_js_path}")

    _, _, js_refs = asset_refs
    js_text = gopanda_js_path.read_text(encoding="utf-8")

    for stock_ref, role in PANDANET_JS_REF_REPLACEMENTS.items():
        js_text = js_text.replace(stock_ref, js_refs[role])

    gopanda_js_path.write_text(js_text, encoding="utf-8")


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
) -> str:
    transform_entries: list[str] = []
    for role in (AssetRole.STONE_BLACK, AssetRole.STONE_WHITE):
        transform = stone_transforms.get(role)
        js_ref = js_refs.get(role)
        if transform is None or js_ref is None:
            continue
        transform_entries.append(
            "    "
            + _js_string_literal(js_ref)
            + ": "
            + _js_runtime_transform_object(transform)
        )

    transforms_block = ",\n".join(transform_entries)
    return (
        "(function(){\n"
        "  var proto = CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;\n"
        "  if (!proto) return;\n"
        "  if (proto.__pandanetThemeReplacerDrawImagePatched) return;\n"
        "  var transforms = {\n"
        f"{transforms_block}\n"
        "  };\n"
        "  var originalDrawImage = proto.drawImage;\n"
        "  function resolveTransform(image) {\n"
        "    if (!image) return null;\n"
        "    var src = typeof image.currentSrc === 'string' && image.currentSrc ? image.currentSrc : image.src;\n"
        "    if (typeof src !== 'string') return null;\n"
        "    for (var key in transforms) {\n"
        "      if (Object.prototype.hasOwnProperty.call(transforms, key) && src.indexOf(key) !== -1) return transforms[key];\n"
        "    }\n"
        "    return null;\n"
        "  }\n"
        "  proto.drawImage = function(image, dx, dy, dw, dh) {\n"
        "    if (arguments.length === 5) {\n"
        "      var transform = resolveTransform(image);\n"
        "      if (transform) {\n"
        "        return originalDrawImage.call(\n"
        "          this,\n"
        "          image,\n"
        "          dx + (dw * transform.left / 100),\n"
        "          dy + (dh * transform.top / 100),\n"
        "          dw * transform.width / 100,\n"
        "          dh * transform.height / 100\n"
        "        );\n"
        "      }\n"
        "    }\n"
        "    return originalDrawImage.apply(this, arguments);\n"
        "  };\n"
        "  proto.__pandanetThemeReplacerDrawImagePatched = true;\n"
        "}());\n"
    )


def _js_runtime_transform_object(transform: StoneTransform) -> str:
    return (
        "{ "
        f"left: {_percent_number(transform.left)}, "
        f"top: {_percent_number(transform.top)}, "
        f"width: {_percent_number(transform.width)}, "
        f"height: {_percent_number(transform.height)} "
        "}"
    )


def _js_string_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _percent_number(value: str) -> str:
    return format(float(value.removesuffix("%")), "g")
