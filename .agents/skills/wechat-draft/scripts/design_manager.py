"""
design_manager.py - WeChat 草稿设计灵感模块

从 design/ 目录随机选取一份设计文档，解析其中的颜色和风格信息，
生成公众号兼容的 CSS 覆盖层，为草稿注入差异化的视觉气质。

每次调用 pick_random_design() 时随机选取一份设计文档并解析，
生成的 CSS 通过 generate_design_css() 输出，由 publish_draft.py
在正式 CSS 内联流程中叠加到现有样式预设之上。
"""

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DESIGN_DIR = Path(__file__).parent.parent / "design"


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------


def _extract_color(value: str) -> Optional[str]:
    """Extract the first usable color value from a Quick Color Reference bullet value.

    Precedence:
    1. Hex color inside backticks: ``#5e6ad2``
    2. ``rgba(...)`` or ``rgb(...)`` anywhere in the string
    3. Bare hex color token: #5e6ad2
    """
    m = re.search(r"`(#[0-9a-fA-F]{3,8})`", value)
    if m:
        return m.group(1)
    m = re.search(r"(rgba?\([^)]+\))", value)
    if m:
        return m.group(1)
    m = re.search(r"(#[0-9a-fA-F]{6,8})\b", value)
    if m:
        return m.group(1)
    return None


def _is_dark_color(hex_color: str) -> bool:
    """Return True when the hex color has relative luminance below 0.18 (dark)."""
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) < 6:
        return False
    try:
        r, g, b = (int(c[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

        def _lin(x: float) -> float:
            return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

        L = 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)
        return L < 0.18
    except ValueError:
        return False


def _is_white_based_rgba(color: str) -> bool:
    """Return True for rgba(255,255,255,...) which is invisible on a white WeChat background."""
    return bool(re.match(r"rgba\s*\(\s*2[4-5]\d\s*,\s*2[4-5]\d\s*,\s*2[4-5]\d\s*,", color))


def _hex_to_rgba(hex_color: str, alpha: float) -> Optional[str]:
    """Convert #RRGGBB to rgba(r,g,b,alpha). Returns None on parse failure."""
    c = hex_color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return None
    try:
        r, g, b = (int(c[i : i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{alpha})"
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Label → semantic role classification
# ---------------------------------------------------------------------------


def _match_label(label: str) -> Optional[str]:
    """Map a Quick Color Reference label string to a semantic role, or return None.

    More-specific patterns are checked first so a label like "page background"
    is caught before the generic "background" catch.
    """
    label = label.strip().lower()
    checks: List[Tuple[str, str]] = [
        ("primary cta", "cta"),
        ("brand accent", "brand"),
        ("page background", "background"),
        ("heading text", "heading"),
        ("body text", "body"),
        ("secondary text", "secondary"),
        ("muted text", "secondary"),
        ("link hover", "link"),
        ("focus ring", "focus"),
        ("alt background", "surface"),
        ("panel background", "surface"),
        # Generic fallbacks — intentionally after the more-specific ones
        ("background", "background"),
        ("heading", "heading"),
        ("brand", "brand"),
        ("accent", "brand"),
        ("link", "link"),
        ("body", "body"),
        ("text", "body"),
        ("secondary", "secondary"),
        ("surface", "surface"),
        ("border", "border"),
        ("focus", "focus"),
    ]
    for pattern, role in checks:
        if pattern in label:
            return role
    return None


# ---------------------------------------------------------------------------
# Design document parsing
# ---------------------------------------------------------------------------


def _parse_quick_color_reference(text: str) -> Dict[str, str]:
    """Parse the '### Quick Color Reference' section into role → color_value mapping.

    First match per role wins (light-theme variants appear first in every doc).
    """
    colors: Dict[str, str] = {}
    in_section = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == "### Quick Color Reference":
            in_section = True
            continue
        if in_section:
            if stripped.startswith("##"):
                break
            if stripped.startswith("- ") and ":" in stripped:
                rest = stripped[2:]
                label, _, val = rest.partition(":")
                role = _match_label(label)
                if role:
                    color = _extract_color(val.strip())
                    if color and role not in colors:
                        colors[role] = color
    return colors


def _parse_key_characteristics(text: str) -> List[str]:
    """Return up to six bullet points from the '**Key Characteristics:**' block."""
    traits: List[str] = []
    in_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if "**Key Characteristics:**" in stripped:
            in_block = True
            continue
        if in_block:
            if stripped.startswith("- "):
                traits.append(stripped[2:])
            elif stripped and not stripped.startswith("-"):
                break
    return traits[:6]


# ---------------------------------------------------------------------------
# DesignProfile dataclass
# ---------------------------------------------------------------------------

_FALLBACK_HEADING = "#18202a"
_FALLBACK_LINK = "#175fe6"
_FALLBACK_ACCENT = "#6f86ff"
_FALLBACK_SECONDARY = "#4e5a6b"
_FALLBACK_SURFACE = "#f5f5f5"
_FALLBACK_BORDER = "#d9e0ea"


@dataclass
class DesignProfile:
    """Fully-resolved WeChat-compatible design token set derived from a design markdown doc.

    All ``css_*`` fields are ready for direct use in inline CSS on a white background.
    """

    name: str           # File stem, e.g. "apple"
    display_name: str   # Human-readable, e.g. "Apple"
    is_dark: bool       # Whether the original design is a dark-themed system

    css_heading: str    # Color for h1–h6 and strong
    css_link: str       # Color for <a> elements
    css_accent: str     # Blockquote / decorative accent color
    css_secondary: str  # Blockquote text, muted tone
    css_surface: str    # Table header background
    css_border: str     # hr, table, divider border color

    key_traits: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Profile resolution helpers
# ---------------------------------------------------------------------------


def _safe_color(color: Optional[str], fallback: str) -> str:
    """Return *color* when it is usable on a white background, else *fallback*."""
    if not color:
        return fallback
    if color.startswith("rgba") or color.startswith("rgb("):
        if _is_white_based_rgba(color):
            return fallback
        return color
    return color


def load_design_profile(path: Path) -> DesignProfile:
    """Parse a design markdown file into a fully-resolved DesignProfile.

    Dark-themed designs (Linear, Spotify …) are adapted for WeChat's white
    background by using their vivid accent color as the primary personality
    color for headings and decorative elements.
    """
    text = path.read_text(encoding="utf-8")
    raw = _parse_quick_color_reference(text)
    traits = _parse_key_characteristics(text)
    name = path.stem
    display_name = name.capitalize()

    bg_color = raw.get("background", "#ffffff")
    is_dark = not bg_color.startswith("rgba") and _is_dark_color(bg_color)

    # Resolve accent: brand > cta > fallback
    accent = raw.get("brand") or raw.get("cta") or _FALLBACK_ACCENT

    # Resolve link color: link > brand > cta > fallback
    link = raw.get("link") or raw.get("brand") or raw.get("cta") or _FALLBACK_LINK

    if is_dark:
        # Dark designs: use accent as personality color on the white WeChat canvas.
        # Body / secondary from the dark palette would be illegible on white, so we
        # adapt: headings and links take the vivid accent, text stays dark.
        css_heading = accent
        css_link = link
        css_accent = accent
        css_secondary = _safe_color(raw.get("secondary"), _FALLBACK_SECONDARY)
        css_surface = _FALLBACK_SURFACE
        raw_border = raw.get("border", "")
        if raw_border and not raw_border.startswith("rgba") and not _is_white_based_rgba(raw_border):
            # Use hex borders from dark designs only if they're visible on white
            css_border = raw_border if not _is_dark_color(raw_border) else _FALLBACK_BORDER
        else:
            css_border = _FALLBACK_BORDER
    else:
        # Light designs: use extracted colors directly, with safe fallbacks.
        raw_heading = raw.get("heading", _FALLBACK_HEADING)
        css_heading = raw_heading if not raw_heading.startswith("rgba") else "#1a1a1a"
        css_link = _safe_color(link, _FALLBACK_LINK)
        css_accent = accent
        raw_secondary = raw.get("secondary", _FALLBACK_SECONDARY)
        css_secondary = raw_secondary if not raw_secondary.startswith("rgba") else _FALLBACK_SECONDARY
        raw_surface = raw.get("surface", _FALLBACK_SURFACE)
        css_surface = _safe_color(raw_surface, _FALLBACK_SURFACE)
        css_border = _safe_color(raw.get("border"), _FALLBACK_BORDER)

    return DesignProfile(
        name=name,
        display_name=display_name,
        is_dark=is_dark,
        css_heading=css_heading,
        css_link=css_link,
        css_accent=css_accent,
        css_secondary=css_secondary,
        css_surface=css_surface,
        css_border=css_border,
        key_traits=traits,
    )


def pick_random_design() -> DesignProfile:
    """Randomly select one design document from the design/ directory and parse it."""
    design_files = sorted(DESIGN_DIR.glob("*.md"))
    if not design_files:
        raise FileNotFoundError(f"design/ 目录下未找到设计文档: {DESIGN_DIR}")
    chosen = random.choice(design_files)
    return load_design_profile(chosen)


# ---------------------------------------------------------------------------
# CSS overlay generation
# ---------------------------------------------------------------------------


def generate_design_css(profile: DesignProfile) -> str:
    """Generate a WeChat-compatible CSS overlay string from *profile*.

    The returned CSS string is designed to be concatenated after the base
    style-preset CSS and applied in a single ``apply_inline_css`` pass, so
    equal-specificity rules here win over preset rules (later source order
    wins at equal specificity in the cascade).

    Only properties that are stable in WeChat inline HTML are touched:
    heading/link/strong colors, blockquote styling, hr/table borders.
    """
    # Blockquote background: 6% tinted accent for subtle personality
    bq_bg = "#f5f5f5"
    if not profile.css_accent.startswith("rgba"):
        bq_bg = _hex_to_rgba(profile.css_accent, 0.06) or "#f5f5f5"

    lines = [
        f"/* design-overlay: {profile.display_name} */",
        f".wechat-article-body h1 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body h2 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body h3 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body h4 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body h5 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body h6 {{ color: {profile.css_heading}; }}",
        f".wechat-article-body a {{ color: {profile.css_link}; }}",
        f".wechat-article-body strong {{ color: {profile.css_heading}; }}",
        (
            f".wechat-article-body blockquote {{"
            f" border-left: 4px solid {profile.css_accent};"
            f" background: {bq_bg};"
            f" color: {profile.css_secondary};"
            f" }}"
        ),
        f".wechat-article-body hr {{ border-top: 1px solid {profile.css_border}; }}",
        f".wechat-article-body th {{ background: {profile.css_surface}; border: 1px solid {profile.css_border}; }}",
        f".wechat-article-body td {{ border: 1px solid {profile.css_border}; }}",
    ]
    return "\n".join(lines)
