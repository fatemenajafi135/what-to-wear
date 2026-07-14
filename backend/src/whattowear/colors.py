"""Color model: hex is the source of truth; names are derived, not stored.

Why: a name ("navy") and a hex ("#1b2a4a") entered independently drift apart
over time with no safeguard. Storing hex only and deriving the name on demand
(nearest-neighbor lookup against a curated palette) makes that drift
structurally impossible — there is exactly one place color data lives.

Why a curated palette instead of a generic name library (e.g. CSS3/webcolors):
this project's vocabulary is fashion-specific ("camel", "oatmeal", "charcoal"),
which generic 147-name web-color lists don't cover — the same "generic model
doesn't know fashion terms" problem the RAG-handoff flags for embeddings
applies here too. Extend FASHION_COLOR_PALETTE as new colors show up in data.

Also implements the WCAG 2.x contrast-ratio formula, repurposed here as an
objective, computable proxy for how much two garment colors "pop" together —
NOT for UI text/background accessibility (no frontend this phase). It sits
alongside the subjective L1 rule text (Chevreul's simultaneous contrast, etc.)
as a numeric signal the generator or a future scorer can reason with.
"""

from __future__ import annotations

import re

# name -> hex. Every color name currently used in data/fixtures/wardrobe.json
# is covered exactly (not approximated) — see the repo guide for the source list.
FASHION_COLOR_PALETTE: dict[str, str] = {
    # neutrals
    "black": "#000000",
    "white": "#ffffff",
    "grey": "#808080",
    "charcoal": "#36454f",
    "navy": "#1b2a4a",
    "beige": "#c8ad7f",
    "cream": "#fffdd0",
    "ivory": "#fffff0",
    "tan": "#d2b48c",
    "khaki": "#c3b091",
    "camel": "#c19a6b",
    "oatmeal": "#ded0b6",
    "taupe": "#8b8589",
    "brown": "#5c4033",
    # blues
    "light blue": "#add8e6",
    "cobalt": "#0047ab",
    "denim blue": "#1560bd",
    "indigo denim": "#2f3a56",
    "black denim": "#1c1c1e",
    # greens
    "emerald green": "#046307",
    "sage": "#9caf88",
    "olive": "#708238",
    "pistachio": "#93c572",
    # reds / pinks
    "tomato red": "#ff6347",
    "terracotta": "#e2725b",
    "burgundy": "#800020",
    "blush pink": "#de5d83",
    # yellows / oranges
    "butter yellow": "#f4e99b",
    "mustard": "#ffdb58",
    "rust": "#b7410e",
    # purples
    "lavender": "#e6e6fa",
    "plum": "#8e4585",
    # metallics
    "gold": "#d4af37",
    "silver": "#c0c0c0",
}

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def is_hex(value: str) -> bool:
    return bool(_HEX_RE.match(value))


def normalize_hex(value: str) -> str:
    """'#RRGGBB' or 'RRGGBB' (any case) -> canonical lowercase '#rrggbb'."""
    if not is_hex(value):
        raise ValueError(
            f"{value!r} is not a valid hex color. If you meant a name, look it "
            f"up in colors.FASHION_COLOR_PALETTE (or add it there)."
        )
    return "#" + value.lstrip("#").lower()


def name_to_hex(name: str) -> str:
    """Curated palette lookup. Raises if the name isn't defined — add it to
    FASHION_COLOR_PALETTE rather than guessing a value."""
    key = name.strip().lower()
    if key not in FASHION_COLOR_PALETTE:
        raise KeyError(f"{name!r} not in FASHION_COLOR_PALETTE — add it there")
    return FASHION_COLOR_PALETTE[key]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = normalize_hex(hex_color).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def nearest_name(hex_color: str) -> str:
    """Nearest-neighbor (Euclidean RGB) name for a hex value — the derived,
    human/search-friendly label. Approximate by design: precision lives in the
    hex; the name only needs to be good enough for text search and prompts."""
    r, g, b = _hex_to_rgb(hex_color)
    best_name, best_dist = "unknown", float("inf")
    for name, h in FASHION_COLOR_PALETTE.items():
        pr, pg, pb = _hex_to_rgb(h)
        dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name


def nearest_names(hex_colors: list[str]) -> list[str]:
    return [nearest_name(h) for h in hex_colors]


# --- WCAG 2.x contrast ratio, repurposed as an objective harmony signal ------


def _relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance over linearized (gamma-corrected) sRGB channels."""
    r, g, b = (c / 255 for c in _hex_to_rgb(hex_color))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(r), lin(g), lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio: 1.0 (identical) to 21.0 (black vs white)."""
    l1 = _relative_luminance(hex_a)
    l2 = _relative_luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def contrast_hint(hex_a: str, hex_b: str) -> str:
    """A short descriptive label pairing the computed ratio with a styling
    read — meant to sit beside the subjective L1 rule text as a numeric signal."""
    ratio = contrast_ratio(hex_a, hex_b)
    if ratio >= 4.5:
        return f"high contrast ({ratio:.1f}:1) — a bold, statement pairing"
    if ratio >= 2.0:
        return f"moderate contrast ({ratio:.1f}:1) — a balanced pairing"
    return f"low contrast ({ratio:.1f}:1) — a tonal, subtle pairing"
