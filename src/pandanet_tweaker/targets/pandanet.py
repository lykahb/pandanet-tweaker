from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import random

from pandanet_tweaker.models import AssetRole, ThemeAsset

DEFAULT_ASAR_DIR = Path("/Applications/GoPanda2.app/Contents/Resources")
DEFAULT_ASAR_PATH = Path("/Applications/GoPanda2.app/Contents/Resources/app.asar")
DEFAULT_ORIGINAL_ASAR_PATH = Path("/Applications/GoPanda2.app/Contents/Resources/original-app.asar")
PANDANET_INDEX_HTML_PATH = Path("app/index.html")
PANDANET_SITE_CSS_PATH = Path("app/css/site.css")
PANDANET_GOPANDA_JS_PATH = Path("app/js/gopanda.js")
PANDANET_THEME_RUNTIME_JS_PATH = Path("app/js/pandanet-tweaker.js")
PANDANET_THEME_RUNTIME_SCRIPT_SRC = "js/pandanet-tweaker.js"
PANDANET_CUSTOM_ASSET_DIR = Path("app/img/custom")
PANDANET_GOBAN_GRID_SELECTOR = ".goban > .grid-canvas"
PANDANET_GOBAN_SHADOW_SELECTOR = ".goban canvas.shadow-canvas"

PANDANET_THEME_STOCK_REFS: dict[AssetRole, str] = {
    AssetRole.BOARD: "../img/wood-board.jpg",
    AssetRole.STONE_BLACK: "img/50/stone-black.png",
    AssetRole.STONE_WHITE: "img/50/stone-white.png",
}

PANDANET_CSS_REF_REPLACEMENTS: dict[str, AssetRole] = {
    "../img/wood-board.jpg": AssetRole.BOARD,
    "../img/50/stone-black-w-shadow.png": AssetRole.STONE_BLACK,
    "../img/50/stone-white-w-shadow.png": AssetRole.STONE_WHITE,
    "../img/50/stone-black.png": AssetRole.STONE_BLACK,
    "../img/50/stone-white.png": AssetRole.STONE_WHITE,
}

PANDANET_JS_REF_REPLACEMENTS: dict[str, AssetRole] = {
    "img/50/stone-black.png": AssetRole.STONE_BLACK,
    "img/50/stone-white.png": AssetRole.STONE_WHITE,
}


def resolve_source_asar_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        return explicit_path.expanduser()

    if DEFAULT_ORIGINAL_ASAR_PATH.is_file():
        return DEFAULT_ORIGINAL_ASAR_PATH

    return DEFAULT_ASAR_PATH


def target_path_for_asset(asset: ThemeAsset) -> Path:
    return PANDANET_CUSTOM_ASSET_DIR / asset.filename


def css_ref_for_asset(asset: ThemeAsset) -> str:
    return f"../img/custom/{asset.filename}"


def js_ref_for_asset(asset: ThemeAsset) -> str:
    return f"img/custom/{asset.filename}"


@dataclass(frozen=True)
class GridCanvasFilter:
    target_rgba: tuple[int, int, int, int]
    predicted_rgb: tuple[int, int, int]
    filter_css: str
    opacity_css: str
    filter_values: tuple[float, float, float, float, float, float]
    loss: float


def grid_rgba_to_css_filter(hex_value: str) -> GridCanvasFilter:
    target_rgba = _parse_hex_rgba(hex_value)
    solver = _FilterSolver(target_rgba[:3], random.Random(0))
    values, loss = solver.solve()
    predicted_rgb = solver.apply(values)
    opacity_css = format(target_rgba[3] / 255, ".3f").rstrip("0").rstrip(".") or "0"
    return GridCanvasFilter(
        target_rgba=target_rgba,
        predicted_rgb=predicted_rgb,
        filter_css=_format_filter_css(values),
        opacity_css=opacity_css,
        filter_values=values,
        loss=loss,
    )


def _parse_hex_rgba(value: str) -> tuple[int, int, int, int]:
    compact = value.strip()
    if compact.startswith("#"):
        compact = compact[1:]

    if len(compact) in {3, 4}:
        compact = "".join(ch * 2 for ch in compact)

    if len(compact) == 6:
        compact += "ff"

    if len(compact) != 8 or any(ch not in "0123456789abcdefABCDEF" for ch in compact):
        raise ValueError("expected a hex color in #RRGGBB or #RRGGBBAA form")

    return tuple(int(compact[index : index + 2], 16) for index in range(0, 8, 2))


def _format_filter_css(values: tuple[float, float, float, float, float, float]) -> str:
    return (
        f"invert({round(values[0])}%) "
        f"sepia({round(values[1])}%) "
        f"saturate({round(values[2])}%) "
        f"hue-rotate({round(values[3] * 3.6)}deg) "
        f"brightness({round(values[4])}%) "
        f"contrast({round(values[5])}%)"
    )


class _Color:
    def __init__(self, r: float, g: float, b: float) -> None:
        self.r = r
        self.g = g
        self.b = b

    def set(self, r: float, g: float, b: float) -> None:
        self.r = self._clamp(r)
        self.g = self._clamp(g)
        self.b = self._clamp(b)

    def invert(self, value: float = 1.0) -> None:
        self.r = self._clamp((value + self.r / 255 * (1 - 2 * value)) * 255)
        self.g = self._clamp((value + self.g / 255 * (1 - 2 * value)) * 255)
        self.b = self._clamp((value + self.b / 255 * (1 - 2 * value)) * 255)

    def sepia(self, value: float = 1.0) -> None:
        self._multiply(
            (
                0.393 + 0.607 * (1 - value),
                0.769 - 0.769 * (1 - value),
                0.189 - 0.189 * (1 - value),
                0.349 - 0.349 * (1 - value),
                0.686 + 0.314 * (1 - value),
                0.168 - 0.168 * (1 - value),
                0.272 - 0.272 * (1 - value),
                0.534 - 0.534 * (1 - value),
                0.131 + 0.869 * (1 - value),
            )
        )

    def saturate(self, value: float = 1.0) -> None:
        self._multiply(
            (
                0.213 + 0.787 * value,
                0.715 - 0.715 * value,
                0.072 - 0.072 * value,
                0.213 - 0.213 * value,
                0.715 + 0.285 * value,
                0.072 - 0.072 * value,
                0.213 - 0.213 * value,
                0.715 - 0.715 * value,
                0.072 + 0.928 * value,
            )
        )

    def hue_rotate(self, angle: float = 0.0) -> None:
        radians = angle / 180 * math.pi
        sine = math.sin(radians)
        cosine = math.cos(radians)
        self._multiply(
            (
                0.213 + cosine * 0.787 - sine * 0.213,
                0.715 - cosine * 0.715 - sine * 0.715,
                0.072 - cosine * 0.072 + sine * 0.928,
                0.213 - cosine * 0.213 + sine * 0.143,
                0.715 + cosine * 0.285 + sine * 0.140,
                0.072 - cosine * 0.072 - sine * 0.283,
                0.213 - cosine * 0.213 - sine * 0.787,
                0.715 - cosine * 0.715 + sine * 0.715,
                0.072 + cosine * 0.928 + sine * 0.072,
            )
        )

    def brightness(self, value: float = 1.0) -> None:
        self._linear(value)

    def contrast(self, value: float = 1.0) -> None:
        self._linear(value, -(0.5 * value) + 0.5)

    def hsl(self) -> tuple[float, float, float]:
        r = self.r / 255
        g = self.g / 255
        b = self.b / 255
        maximum = max(r, g, b)
        minimum = min(r, g, b)
        lightness = (maximum + minimum) / 2

        if maximum == minimum:
            return (0.0, 0.0, lightness * 100)

        delta = maximum - minimum
        saturation = delta / (2 - maximum - minimum) if lightness > 0.5 else delta / (maximum + minimum)
        if maximum == r:
            hue = (g - b) / delta + (6 if g < b else 0)
        elif maximum == g:
            hue = (b - r) / delta + 2
        else:
            hue = (r - g) / delta + 4

        return (hue * 60, saturation * 100, lightness * 100)

    def _linear(self, slope: float = 1.0, intercept: float = 0.0) -> None:
        self.r = self._clamp(self.r * slope + intercept * 255)
        self.g = self._clamp(self.g * slope + intercept * 255)
        self.b = self._clamp(self.b * slope + intercept * 255)

    def _multiply(self, matrix: tuple[float, ...]) -> None:
        r = self._clamp(self.r * matrix[0] + self.g * matrix[1] + self.b * matrix[2])
        g = self._clamp(self.r * matrix[3] + self.g * matrix[4] + self.b * matrix[5])
        b = self._clamp(self.r * matrix[6] + self.g * matrix[7] + self.b * matrix[8])
        self.r, self.g, self.b = r, g, b

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(255.0, value))


class _FilterSolver:
    def __init__(self, target_rgb: tuple[int, int, int], rng: random.Random) -> None:
        self.target = _Color(*target_rgb)
        self.target_hsl = self.target.hsl()
        self.rng = rng

    def solve(self) -> tuple[tuple[float, float, float, float, float, float], float]:
        wide_values, wide_loss = self._spsa(
            A=5,
            a=(60, 180, 18000, 600, 1.2, 1.2),
            c=15,
            values=(50, 20, 3750, 50, 100, 100),
            iterations=1000,
        )
        return self._spsa(
            A=wide_loss,
            a=(
                0.25 * (wide_loss + 1),
                0.25 * (wide_loss + 1),
                wide_loss + 1,
                0.25 * (wide_loss + 1),
                0.2 * (wide_loss + 1),
                0.2 * (wide_loss + 1),
            ),
            c=2,
            values=wide_values,
            iterations=500,
        )

    def apply(self, values: tuple[float, float, float, float, float, float]) -> tuple[int, int, int]:
        color = _Color(0, 0, 0)
        color.invert(values[0] / 100)
        color.sepia(values[1] / 100)
        color.saturate(values[2] / 100)
        color.hue_rotate(values[3] * 3.6)
        color.brightness(values[4] / 100)
        color.contrast(values[5] / 100)
        return (round(color.r), round(color.g), round(color.b))

    def _loss(self, values: tuple[float, float, float, float, float, float]) -> float:
        color = _Color(0, 0, 0)
        color.invert(values[0] / 100)
        color.sepia(values[1] / 100)
        color.saturate(values[2] / 100)
        color.hue_rotate(values[3] * 3.6)
        color.brightness(values[4] / 100)
        color.contrast(values[5] / 100)
        hue, saturation, lightness = color.hsl()
        target_hue, target_saturation, target_lightness = self.target_hsl
        return (
            abs(color.r - self.target.r)
            + abs(color.g - self.target.g)
            + abs(color.b - self.target.b)
            + abs(hue - target_hue)
            + abs(saturation - target_saturation)
            + abs(lightness - target_lightness)
        )

    def _spsa(
        self,
        *,
        A: float,
        a: tuple[float, float, float, float, float, float],
        c: float,
        values: tuple[float, float, float, float, float, float],
        iterations: int,
    ) -> tuple[tuple[float, float, float, float, float, float], float]:
        alpha = 1
        gamma = 1 / 6
        current = list(values)
        best = tuple(values)
        best_loss = float("inf")

        for index in range(iterations):
            ck = c / ((index + 1) ** gamma)
            deltas = [1 if self.rng.random() > 0.5 else -1 for _ in range(6)]
            high = [current[item] + ck * deltas[item] for item in range(6)]
            low = [current[item] - ck * deltas[item] for item in range(6)]
            loss_diff = self._loss(tuple(high)) - self._loss(tuple(low))

            for item in range(6):
                gradient = loss_diff / (2 * ck) * deltas[item]
                ak = a[item] / ((A + index + 1) ** alpha)
                current[item] = self._fix(current[item] - ak * gradient, item)

            loss = self._loss(tuple(current))
            if loss < best_loss:
                best = tuple(current)
                best_loss = loss

        return best, best_loss

    @staticmethod
    def _fix(value: float, index: int) -> float:
        maximum = 100
        if index == 2:
            maximum = 7500
        elif index in {4, 5}:
            maximum = 200

        if index == 3:
            value %= 100
        else:
            value = max(0.0, min(maximum, value))

        return value
