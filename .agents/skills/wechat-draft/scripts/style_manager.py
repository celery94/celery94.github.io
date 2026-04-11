"""
style_manager.py - 样式管理模块

负责微信公众号文章的样式加载、CSS 内联处理、HTML 净化，以及基于内容自动推断最佳样式预设。

样式预设:
  auto    — 根据文章内容和标签自动推断
  default — 通用微信排版风格（仅 base.css）
  code    — 代码密集型文章（base + code.css 增强代码排版）
  essay   — 散文/观点型文章（base + essay.css 更大字号更宽松间距）
  guide   — 教程/指南型文章（base + guide.css 突出步骤和标题层级）
  none    — 不应用任何样式
  wechat  — 等同于 default（向后兼容别名）

自定义样式: 可将自定义 CSS 文件放入 styles/ 目录，通过 --style-preset 按文件名引用。
"""

import html
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Comment

# ---------------------------------------------------------------------------
# CSS specificity helpers
# ---------------------------------------------------------------------------


def calc_css_specificity(selector: str) -> Tuple[int, int, int]:
    """Return the CSS specificity (ids, classes, elements) for a simple selector.

    Only covers the subset of selectors used in our CSS files: descendant
    combinations of tag names, class selectors, and ID selectors.  Pseudo-
    classes and attribute selectors are filtered out before we reach here.
    """
    ids = 0
    classes = 0
    elements = 0
    # Split on whitespace and combinators (>, +, ~) to get simple selectors
    for part in re.split(r"[\s>+~]+", selector.strip()):
        if not part:
            continue
        ids += part.count("#")
        classes += part.count(".")
        # Strip class/id/attribute fragments to reveal the bare tag name
        tag_part = re.sub(r"[.#\[].*", "", part)
        if tag_part and tag_part != "*":
            elements += 1
    return (ids, classes, elements)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STYLES_DIR = Path(__file__).parent / "styles"

STYLE_NAMES = ("auto", "default", "code", "essay", "guide", "none")

UNSUPPORTED_TAGS = {
    "script",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "button",
    "textarea",
    "select",
    "link",
    "meta",
    "base",
}

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]+)\}")

# Tag sets used for style inference
_CODE_TAGS = {
    "c#", ".net", "python", "javascript", "typescript", "java", "golang",
    "go", "rust", "c++", "kotlin", "swift", "php", "ruby",
    "postgresql", "mysql", "redis", "docker", "kubernetes", "rabbitmq",
    "mongodb", "elasticsearch", "nginx", "linux",
    "asp.net", "asp.net core", "node.js", "react", "angular", "vue",
    "spring", "django", "flask", "fastapi",
    "performance", "benchmark", "optimization", "algorithm", "database",
    "api", "microservices", "async", "concurrency", "memory",
    "profiling", "ef core", "linq", "性能优化", "design patterns",
    "architecture", "clean architecture", "cqrs", "ddd", "devops",
    "ci/cd", "testing", "unit test", "integration test",
}

_ESSAY_TAGS = {
    "ai", "economy", "philosophy", "optimism", "opinion", "technology",
    "future", "society", "career", "思考", "随想", "感悟", "life",
    "culture", "history", "productivity", "management", "leadership",
    "business", "startup", "innovation", "education",
}

_GUIDE_TAGS = {
    "guide", "tutorial", "beginner", "getting started", "best practices",
    "how-to", "tips", "walkthrough", "introduction", "入门", "教程", "实践",
    "step by step", "quickstart", "overview", "hands-on",
}


# ---------------------------------------------------------------------------
# Style loading
# ---------------------------------------------------------------------------


def load_style_css(style_name: str) -> str:
    """Return the CSS text for the given style preset.

    For ``"none"`` returns an empty string.
    For ``"default"`` (or alias ``"wechat"``): returns only ``base.css``.
    For any other named preset: returns ``base.css`` concatenated with the
    matching overlay file (``{style_name}.css``).
    For an unknown name that isn't a file in ``styles/``: falls back to
    ``"default"`` behaviour so the article always gets base styling.
    """
    if style_name == "none":
        return ""

    # Backward-compat alias
    if style_name == "wechat":
        style_name = "default"

    base_path = STYLES_DIR / "base.css"
    try:
        css = base_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        css = ""

    if style_name != "default":
        overlay_path = STYLES_DIR / f"{style_name}.css"
        if overlay_path.exists():
            css += "\n" + overlay_path.read_text(encoding="utf-8")

    return css


# ---------------------------------------------------------------------------
# Style inference
# ---------------------------------------------------------------------------


def extract_frontmatter_tags(md_text: str) -> List[str]:
    """Extract the ``tags`` list from YAML frontmatter (best-effort, no YAML parser needed)."""
    match = re.match(r"^---\s*\n(.*?)\n---", md_text, re.DOTALL)
    if not match:
        return []
    frontmatter = match.group(1)

    # Inline array: tags: ["tag1", "tag2"]  or  tags: ['tag1', 'tag2']
    inline_m = re.search(r"^tags\s*:\s*\[([^\]]+)\]", frontmatter, re.MULTILINE)
    if inline_m:
        return re.findall(r'["\']([^"\']+)["\']', inline_m.group(1))

    # Block list:
    #   tags:
    #     - tag1
    #     - tag2
    block_m = re.search(r"^tags\s*:\s*\n((?:\s+-.+\n?)+)", frontmatter, re.MULTILINE)
    if block_m:
        return [
            item.strip().strip("\"'")
            for item in re.findall(r"-\s+(.+)", block_m.group(1))
        ]

    return []


def infer_style(
    content: str,
    title: str = "",
    tags: Optional[List[str]] = None,
) -> str:
    """Infer the best style preset from content signals and metadata.

    Returns one of ``"code"``, ``"essay"``, ``"guide"``, or ``"default"``.
    """
    scores: Dict[str, float] = {"code": 0.0, "essay": 0.0, "guide": 0.0}

    # --- Tag-based signals ---------------------------------------------------
    if tags:
        for tag in tags:
            t = tag.lower().strip()
            if t in _CODE_TAGS:
                scores["code"] += 2
            if t in _ESSAY_TAGS:
                scores["essay"] += 2
            if t in _GUIDE_TAGS:
                scores["guide"] += 2

    # --- Title signals -------------------------------------------------------
    title_lower = title.lower()
    if re.search(
        r"\b(how to|getting started|introduction to|guide to|tutorial|入门|教程|实现|部署)\b",
        title_lower,
    ):
        scores["guide"] += 2
    if re.search(r"\b(why|what|should|future|思考|感悟|随想|浅谈)\b", title_lower):
        scores["essay"] += 1
    if re.search(r"\b(performance|scaling|optimization|benchmark|implement|build)\b", title_lower):
        scores["code"] += 1

    # --- Content signals: fenced code blocks ---------------------------------
    fence_count = len(re.findall(r"^```", content, re.MULTILINE))
    if fence_count >= 5:
        scores["code"] += 5
    elif fence_count >= 3:
        scores["code"] += 3
    elif fence_count >= 1:
        scores["code"] += 1

    # --- Content signals: heading density (guides have many H2/H3) -----------
    heading_count = len(re.findall(r"^#{2,3}\s", content, re.MULTILINE))
    if heading_count >= 7:
        scores["guide"] += 3
    elif heading_count >= 4:
        scores["guide"] += 1

    # --- Content signals: prose density (essay detection) --------------------
    if fence_count == 0:
        # Only consider paragraphs that are not headings, tables, or very short
        paragraphs = [
            p.strip()
            for p in re.split(r"\n\n+", content)
            if p.strip() and not p.strip().startswith(("#", "|", "```"))
        ]
        word_counts = [len(p.split()) for p in paragraphs if len(p.split()) > 15]
        if word_counts:
            avg_words = sum(word_counts) / len(word_counts)
            if avg_words > 90:
                scores["essay"] += 3
            elif avg_words > 60:
                scores["essay"] += 1

    # --- Pick winner ---------------------------------------------------------
    best = max(scores, key=lambda k: scores[k])
    max_score = scores[best]

    # Need at least 2 points to be confident
    if max_score < 2:
        return "default"

    # Tie → default
    sorted_scores = sorted(scores.values(), reverse=True)
    if sorted_scores[0] == sorted_scores[1]:
        return "default"

    return best


# ---------------------------------------------------------------------------
# CSS parsing & inlining
# ---------------------------------------------------------------------------


def parse_style_declarations(style_text: str) -> Dict[str, str]:
    declarations: Dict[str, str] = {}
    for chunk in style_text.split(";"):
        if ":" not in chunk:
            continue
        name, value = chunk.split(":", 1)
        name = name.strip().lower()
        value = value.strip()
        if name and value:
            declarations[name] = value
    return declarations


def serialize_style_declarations(declarations: Dict[str, str]) -> str:
    return "; ".join(f"{name}: {value}" for name, value in declarations.items())


def parse_css_rules(css_text: str) -> List[Tuple[List[str], Dict[str, str]]]:
    cleaned = CSS_COMMENT_RE.sub("", css_text)
    rules: List[Tuple[List[str], Dict[str, str]]] = []

    for selector_text, body_text in CSS_RULE_RE.findall(cleaned):
        declarations = parse_style_declarations(body_text)
        selectors = []
        for selector in (item.strip() for item in selector_text.split(",")):
            if not selector:
                continue
            if any(token in selector for token in ("@", ":", "[")):
                continue
            selectors.append(selector)
        if selectors and declarations:
            rules.append((selectors, declarations))

    return rules


def sanitize_html_fragment(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()

    for tag in soup.find_all(True):
        if tag.name in UNSUPPORTED_TAGS:
            tag.decompose()
            continue

        attrs_to_remove = []
        for attr_name, attr_value in list(tag.attrs.items()):
            lowered = attr_name.lower()
            if lowered.startswith("on"):
                attrs_to_remove.append(attr_name)
                continue
            if (
                lowered in {"src", "href"}
                and isinstance(attr_value, str)
                and attr_value.lower().startswith("javascript:")
            ):
                attrs_to_remove.append(attr_name)
        for attr_name in attrs_to_remove:
            tag.attrs.pop(attr_name, None)


def apply_inline_css(soup: BeautifulSoup, css_text: str) -> None:
    """Apply *css_text* as inline styles onto *soup*, respecting CSS specificity.

    Each property is won by the declaration whose selector has the highest
    specificity.  When two selectors share the same specificity, the later one
    (source order) wins — exactly as the CSS cascade requires.
    """
    rules = parse_css_rules(css_text)
    if not rules:
        return

    all_tags = list(soup.find_all(True))

    # Per-tag: original inline styles (always win at the end)
    original_styles: Dict[int, Dict[str, str]] = {
        id(tag): parse_style_declarations(tag.get("style", "")) for tag in all_tags
    }

    # Per-tag: {prop: (value, specificity_tuple, order_index)}
    # Higher specificity wins; equal specificity → higher order_index wins.
    prop_maps: Dict[int, Dict[str, Tuple[str, Tuple[int, int, int], int]]] = {
        id(tag): {} for tag in all_tags
    }

    for order_idx, (selectors, declarations) in enumerate(rules):
        for selector in selectors:
            spec = calc_css_specificity(selector)
            try:
                matched_tags = soup.select(selector)
            except Exception:
                continue
            for tag in matched_tags:
                prop_map = prop_maps[id(tag)]
                for prop, value in declarations.items():
                    existing = prop_map.get(prop)
                    if existing is None:
                        prop_map[prop] = (value, spec, order_idx)
                    else:
                        _, ex_spec, ex_order = existing
                        if spec > ex_spec or (spec == ex_spec and order_idx >= ex_order):
                            prop_map[prop] = (value, spec, order_idx)

    for tag in all_tags:
        generated = {prop: val for prop, (val, _, _) in prop_maps[id(tag)].items()}
        # Element's own inline style always overrides stylesheet rules
        generated.update(original_styles[id(tag)])
        if generated:
            tag["style"] = serialize_style_declarations(generated)
        else:
            tag.attrs.pop("style", None)


def load_extra_css(extra_css_file: Optional[str]) -> str:
    if not extra_css_file:
        return ""
    with open(extra_css_file, "r", encoding="utf-8") as handle:
        return handle.read()


def build_styled_fragment(
    fragment_html: str, style_preset: str, extra_css: str, design_css: str = ""
) -> str:
    """Wrap *fragment_html* in an article container, sanitize it, and apply
    inline CSS for *style_preset* plus any *design_css* and *extra_css*.

    ``design_css`` is concatenated with the preset CSS in a **single**
    ``apply_inline_css`` pass so that design rules (which come later in the
    combined string) win over preset rules at equal CSS specificity.  User
    ``extra_css`` is applied afterwards so it can still override everything.
    """
    wrapped = f'<article class="wechat-article-body">{fragment_html}</article>'
    soup = BeautifulSoup(wrapped, "html.parser")
    sanitize_html_fragment(soup)

    style_css = load_style_css(style_preset)
    # Combine preset + design overlay in one pass; design comes after preset so
    # later-source-order wins at equal specificity (design ▶ preset).
    combined_preset = "\n".join(layer for layer in (style_css, design_css) if layer)
    if combined_preset:
        apply_inline_css(soup, combined_preset)
    if extra_css:
        apply_inline_css(soup, extra_css)

    for style_tag in soup.find_all("style"):
        style_tag.decompose()

    article = soup.find("article")
    return str(article) if article else str(soup)
