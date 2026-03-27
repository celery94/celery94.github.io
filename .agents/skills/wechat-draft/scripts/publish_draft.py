#!/usr/bin/env python3
"""
publish_draft.py - 将文章发布到微信公众号草稿箱

用法:
  python publish_draft.py \
    --appid YOUR_APPID \
    --secret YOUR_SECRET \
    --title "文章标题" \
    --content "<p>正文</p>" \
    [--content-file /path/to/content.html] \
    [--content-format auto|markdown|html] \
    [--style-preset auto|default|code|essay|guide|none] \
    [--extra-css-file /path/to/extra.css] \
    [--author "作者"] \
    [--digest "摘要"] \
    [--cover-image /path/to/cover.jpg] \
    [--thumb-media-id EXISTING_MEDIA_ID] \
    [--content-source-url https://example.com]

凭据优先级: 命令行参数 > 环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET > .env 文件
样式预设: auto(自动推断) | default(通用) | code(代码密集) | essay(散文) | guide(教程) | none(无样式)
"""

import argparse
import html
import json
import mimetypes
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from style_manager import (
    STYLE_NAMES,
    build_styled_fragment,
    extract_frontmatter_tags,
    infer_style,
    load_extra_css,
)


WECHAT_API_BASE = "https://api.weixin.qq.com"
LIST_RE = re.compile(r"^(\s*)([*+-]|\d+\.)\s+(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```([\w+-]+)?\s*$")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
DASH_METADATA_FENCE_RE = re.compile(r"^\s*-{3,}\s*$")


def configure_console_encoding() -> None:
    """在 Windows 控制台上优先使用 UTF-8，避免帮助文本输出报错。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()


def load_env_from_dotenv() -> None:
    """从当前目录及其父目录中的 .env 文件加载微信凭据。"""
    dotenv_values: Dict[str, str] = {}
    search_dirs = list(reversed([Path.cwd(), *Path.cwd().parents]))

    for directory in search_dirs:
        env_file = directory / ".env"
        if not env_file.exists():
            continue

        try:
            with open(env_file, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].lstrip()
                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key not in {"WECHAT_APP_ID", "WECHAT_APP_SECRET"}:
                        continue

                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                        value = value[1:-1]
                    elif " #" in value:
                        value = value.split(" #", 1)[0].rstrip()

                    if value:
                        dotenv_values[key] = value
        except OSError:
            continue

    for key, value in dotenv_values.items():
        os.environ.setdefault(key, value)


load_env_from_dotenv()


def get_access_token(appid: str, secret: str) -> str:
    """获取微信公众号 access_token。"""
    url = f"{WECHAT_API_BASE}/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "access_token" in data:
        expires_in = data.get("expires_in")
        if expires_in:
            print(f"      token 有效期: {expires_in} 秒")
        return data["access_token"]

    errcode = data.get("errcode")
    errmsg = data.get("errmsg")
    hints: List[str] = []
    if errcode == 40164:
        hints.append("当前 IP 不在白名单中，请到公众号后台添加当前出口 IP。")
    elif errcode in (40001, 40125):
        hints.append("AppSecret 无效，请检查 --secret 或环境变量 WECHAT_APP_SECRET。")

    detail = f"获取 access_token 失败: errcode={errcode}, errmsg={errmsg}"
    if hints:
        detail = f"{detail}\n建议: {' '.join(hints)}"
    raise RuntimeError(detail)


def guess_image_mime_type(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type or "image/jpeg"


def infer_temp_image_suffix(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    suffix = os.path.splitext(parsed.path)[1].lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return suffix

    normalized = content_type.lower()
    if "png" in normalized:
        return ".png"
    if "gif" in normalized:
        return ".gif"
    if "webp" in normalized:
        return ".webp"
    if "bmp" in normalized:
        return ".bmp"
    return ".jpg"


def upload_cover_image(access_token: str, image_path: str, max_retries: int = 3) -> Optional[str]:
    """上传封面图片，返回可用于图文草稿的封面 media_id。"""
    # 草稿接口要求永久素材的封面 media_id，临时素材接口返回的 thumb_media_id
    # 会在 draft/add 时被判定为 invalid media_id。
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"封面图片不存在: {image_path}")

    url = f"{WECHAT_API_BASE}/cgi-bin/material/add_material"
    params = {"access_token": access_token, "type": "thumb"}
    mime_type = guess_image_mime_type(image_path)

    for attempt in range(1, max_retries + 1):
        try:
            with open(image_path, "rb") as handle:
                files = {"media": (os.path.basename(image_path), handle, mime_type)}
                resp = requests.post(url, params=params, files=files, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "media_id" in data:
                return data["media_id"]
            print(
                "      封面上传失败 "
                f"({attempt}/{max_retries}): errcode={data.get('errcode')}, errmsg={data.get('errmsg')}"
            )
        except Exception as exc:
            print(f"      封面上传异常 ({attempt}/{max_retries}): {exc}")

        if attempt < max_retries:
            time.sleep(2 * attempt)

    return None


def upload_inline_image(access_token: str, image_path: str, max_retries: int = 3) -> Optional[str]:
    """上传文章内嵌图片，返回图片 URL。"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"正文图片不存在: {image_path}")

    url = f"{WECHAT_API_BASE}/cgi-bin/media/uploadimg"
    mime_type = guess_image_mime_type(image_path)

    for attempt in range(1, max_retries + 1):
        try:
            with open(image_path, "rb") as handle:
                files = {"media": (os.path.basename(image_path), handle, mime_type)}
                resp = requests.post(
                    url,
                    params={"access_token": access_token},
                    files=files,
                    timeout=30,
                )
            resp.raise_for_status()
            data = resp.json()
            if "url" in data:
                return data["url"]
            print(
                "      正文图片上传失败 "
                f"({attempt}/{max_retries}) - {os.path.basename(image_path)}: "
                f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}"
            )
        except BaseException as exc:
            print(
                "      正文图片上传异常 "
                f"({attempt}/{max_retries}) - {os.path.basename(image_path)}: {exc}"
            )

        if attempt < max_retries:
            time.sleep(2 * attempt)

    return None


def markdown_to_html(md_text: str) -> str:
    """将 Markdown 转为 HTML。优先使用 markdown 库，否则回退到内置转换器。"""
    md_text = preprocess_markdown(md_text)
    try:
        import markdown as markdown_lib

        return markdown_lib.markdown(
            md_text,
            extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
        )
    except ImportError:
        return basic_markdown_to_html(md_text)


def preprocess_markdown(md_text: str) -> str:
    """预处理 Markdown，移除顶部元数据块，并规范参考链接显示。"""
    normalized = md_text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.startswith("\ufeff"):
        normalized = normalized[1:]
    normalized = strip_leading_dash_metadata(normalized)
    return rewrite_reference_links(normalized)


def strip_leading_dash_metadata(md_text: str) -> str:
    """移除顶部由 ----- 包裹的元数据块，仅处理文件开头的第一段。"""
    lines = md_text.split("\n")
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1

    if start >= len(lines) or not DASH_METADATA_FENCE_RE.match(lines[start]):
        return md_text

    end = start + 1
    while end < len(lines):
        if DASH_METADATA_FENCE_RE.match(lines[end]):
            remaining = lines[end + 1 :]
            while remaining and not remaining[0].strip():
                remaining.pop(0)
            return "\n".join(remaining)
        end += 1

    return md_text


_REFERENCE_HEADINGS = {"参考", "参考链接", "references", "reference", "related links"}


def rewrite_reference_links(md_text: str) -> str:
    """在参考章节内将 Markdown 链接替换为纯文本 URL，避免微信不显示超链接。"""
    lines = md_text.split("\n")
    rewritten_lines: List[str] = []
    in_reference_section = False
    reference_heading_level = 0

    for line in lines:
        stripped = line.strip()
        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            heading_level = len(heading_match.group(1))
            heading_text = normalize_heading_text(heading_match.group(2))
            normalized = heading_text.lower().strip()
            if in_reference_section and heading_level <= reference_heading_level and normalized not in _REFERENCE_HEADINGS:
                in_reference_section = False
                reference_heading_level = 0
            if normalized in _REFERENCE_HEADINGS:
                in_reference_section = True
                reference_heading_level = heading_level

        if in_reference_section:
            line = LINK_RE.sub(replace_link_with_plain_text, line)

        rewritten_lines.append(line)

    return "\n".join(rewritten_lines)


def normalize_heading_text(text: str) -> str:
    cleaned = re.sub(r"\s+#+\s*$", "", text).strip()
    return cleaned


def replace_link_with_plain_text(match: re.Match[str]) -> str:
    """将 [label](url) 替换为纯文本，因为微信公众号不显示超链接。"""
    label = match.group(1).strip()
    url = match.group(2).strip()
    return f"{label}: {url}" if label and label != url else url



def basic_markdown_to_html(md_text: str) -> str:
    """简单 Markdown 转换器，覆盖公众号常见内容结构。"""
    normalized = md_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    html_parts: List[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        fence_match = FENCE_RE.match(stripped)
        if fence_match:
            index, block_html = consume_fenced_code(lines, index, fence_match.group(1) or "")
            html_parts.append(block_html)
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            level = len(heading_match.group(1))
            text = render_inline_markdown(heading_match.group(2).strip())
            html_parts.append(f"<h{level}>{text}</h{level}>")
            index += 1
            continue

        if is_table_block(lines, index):
            index, block_html = consume_table(lines, index)
            html_parts.append(block_html)
            continue

        if stripped.startswith(">"):
            index, block_html = consume_blockquote(lines, index)
            html_parts.append(block_html)
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            index, block_html = consume_list(lines, index, len(list_match.group(1)))
            html_parts.append(block_html)
            continue

        if is_horizontal_rule(stripped):
            html_parts.append("<hr />")
            index += 1
            continue

        index, block_html = consume_paragraph(lines, index)
        html_parts.append(block_html)

    return "\n".join(part for part in html_parts if part)


def consume_fenced_code(lines: Sequence[str], start: int, language: str) -> Tuple[int, str]:
    index = start + 1
    code_lines: List[str] = []
    while index < len(lines):
        if FENCE_RE.match(lines[index].strip()):
            index += 1
            break
        code_lines.append(lines[index])
        index += 1

    code_text = html.escape("\n".join(code_lines))
    class_attr = f' class="language-{html.escape(language)}"' if language else ""
    return index, f"<pre><code{class_attr}>{code_text}</code></pre>"


def consume_blockquote(lines: Sequence[str], start: int) -> Tuple[int, str]:
    block_lines: List[str] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith(">"):
            break
        block_lines.append(re.sub(r"^>\s?", "", stripped))
        index += 1

    inner_html = basic_markdown_to_html("\n".join(block_lines)).strip()
    return index, f"<blockquote>{inner_html}</blockquote>"


def consume_list(lines: Sequence[str], start: int, base_indent: int) -> Tuple[int, str]:
    first_match = LIST_RE.match(lines[start])
    if not first_match:
        raise ValueError("内部错误: consume_list 起始行不是列表项")

    ordered = first_match.group(2).endswith(".")
    list_tag = "ol" if ordered else "ul"
    items: List[str] = []
    index = start

    while index < len(lines):
        line = lines[index]
        match = LIST_RE.match(line)
        if not match or len(match.group(1)) != base_indent or match.group(2).endswith(".") != ordered:
            break

        item_lines = [match.group(3)]
        index += 1

        while index < len(lines):
            next_line = lines[index]
            next_match = LIST_RE.match(next_line)
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            if next_match and len(next_match.group(1)) == base_indent and next_match.group(2).endswith(".") == ordered:
                break
            if not next_line.strip():
                item_lines.append("")
                index += 1
                continue
            if next_indent > base_indent:
                item_lines.append(next_line[base_indent + 2 :])
                index += 1
                continue
            break

        item_html = basic_markdown_to_html("\n".join(item_lines).strip()) or render_inline_markdown(item_lines[0].strip())
        if item_html.startswith("<p>") and item_html.endswith("</p>") and item_html.count("<p>") == 1:
            item_html = item_html[3:-4]
        items.append(f"<li>{item_html}</li>")

    return index, f"<{list_tag}>{''.join(items)}</{list_tag}>"


def consume_table(lines: Sequence[str], start: int) -> Tuple[int, str]:
    header_cells = split_table_row(lines[start])
    index = start + 2
    body_rows: List[str] = []

    while index < len(lines):
        current = lines[index]
        if not current.strip() or "|" not in current:
            break
        row_cells = split_table_row(current)
        if not row_cells:
            break
        body_rows.append(
            "<tr>" + "".join(f"<td>{render_inline_markdown(cell)}</td>" for cell in row_cells) + "</tr>"
        )
        index += 1

    header_html = "<tr>" + "".join(f"<th>{render_inline_markdown(cell)}</th>" for cell in header_cells) + "</tr>"
    table_html = f"<table><thead>{header_html}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    return index, table_html


def consume_paragraph(lines: Sequence[str], start: int) -> Tuple[int, str]:
    paragraph_lines: List[str] = []
    index = start

    while index < len(lines):
        current = lines[index]
        stripped = current.strip()
        if not stripped:
            break
        if index != start and is_block_start(lines, index):
            break
        paragraph_lines.append(stripped)
        index += 1

    paragraph_html = "<br />".join(render_inline_markdown(line) for line in paragraph_lines)
    return index, f"<p>{paragraph_html}</p>"


def render_inline_markdown(text: str) -> str:
    inline_tokens: List[str] = []

    def stash_html(fragment: str) -> str:
        inline_tokens.append(fragment)
        return f"@@INLINE{len(inline_tokens) - 1}@@"

    def stash_code(match: re.Match[str]) -> str:
        return stash_html(f"<code>{html.escape(match.group(1))}</code>")

    def stash_image(match: re.Match[str]) -> str:
        alt = html.escape(match.group(1), quote=True)
        src = html.escape(match.group(2), quote=True)
        title = match.group(3)
        title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
        return stash_html(f'<img src="{src}" alt="{alt}"{title_attr} />')

    def stash_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1))
        href = html.escape(match.group(2), quote=True)
        title = match.group(3)
        title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
        return stash_html(f'<a href="{href}"{title_attr}>{label}</a>')

    escaped = CODE_SPAN_RE.sub(stash_code, text)
    escaped = IMAGE_RE.sub(stash_image, escaped)
    escaped = LINK_RE.sub(stash_link, escaped)
    escaped = html.escape(escaped)
    escaped = BOLD_RE.sub(lambda match: f"<strong>{match.group(2)}</strong>", escaped)
    escaped = ITALIC_RE.sub(lambda match: f"<em>{match.group(1) or match.group(2)}</em>", escaped)

    for token_index, fragment in enumerate(inline_tokens):
        escaped = escaped.replace(f"@@INLINE{token_index}@@", fragment)

    return escaped


def is_horizontal_rule(line: str) -> bool:
    compact = line.replace(" ", "")
    return compact in {"---", "***", "___"}


def is_table_block(lines: Sequence[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    header = lines[index]
    separator = lines[index + 1]
    return "|" in header and is_table_separator(separator)


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def split_table_row(line: str) -> List[str]:
    parts = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [part for part in parts if part or len(parts) == 1]


def is_block_start(lines: Sequence[str], index: int) -> bool:
    stripped = lines[index].strip()
    return bool(
        stripped
        and (
            FENCE_RE.match(stripped)
            or HEADING_RE.match(stripped)
            or stripped.startswith(">")
            or LIST_RE.match(lines[index])
            or is_horizontal_rule(stripped)
            or is_table_block(lines, index)
        )
    )


def strip_full_document(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    if soup.body:
        return "".join(str(child) for child in soup.body.contents)
    return raw_html


def is_http_image_url(src: str) -> bool:
    return src.lower().startswith(("http://", "https://"))


def is_wechat_cdn_image(src: str) -> bool:
    parsed = urlparse(src)
    return "mmbiz.qpic.cn" in (parsed.netloc or src)


def download_external_image(url: str) -> Optional[str]:
    """下载外部图片到临时文件，返回本地路径。"""
    normalized_url = html.unescape(url.strip())
    temp_path: Optional[str] = None

    try:
        resp = requests.get(
            normalized_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()

        suffix = infer_temp_image_suffix(normalized_url, resp.headers.get("Content-Type", ""))
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(resp.content)
            temp_path = handle.name
        return temp_path
    except Exception as exc:
        print(f"      外部图片下载失败: {normalized_url[:80]}... ({exc})")
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        return None


def resolve_local_image_path(src: str, source_dir: str) -> Optional[str]:
    trimmed = src.strip()
    if not trimmed or trimmed.startswith("//") or trimmed.lower().startswith(("http://", "https://", "data:")):
        return None

    parsed = urlparse(trimmed)
    candidate = trimmed
    if parsed.scheme == "file":
        candidate = unquote(parsed.path or "")
        if os.name == "nt" and candidate.startswith("/") and re.match(r"^/[A-Za-z]:", candidate):
            candidate = candidate[1:]
    elif parsed.scheme:
        return None

    candidate = unquote(candidate)
    if not os.path.isabs(candidate):
        candidate = os.path.join(source_dir, candidate)
    candidate = os.path.abspath(os.path.normpath(candidate))
    return candidate


def rewrite_inline_images(fragment_html: str, access_token: str, source_dir: str) -> Tuple[str, Dict[str, int]]:
    soup = BeautifulSoup(fragment_html, "html.parser")
    seen_uploads: Dict[str, Optional[str]] = {}
    stats = {
        "total": 0,
        "local": 0,
        "external": 0,
        "skipped": 0,
        "uploaded": 0,
        "failed": 0,
    }

    for image_tag in soup.find_all("img"):
        src = image_tag.get("src", "").strip()
        if not src:
            continue

        stats["total"] += 1

        if is_wechat_cdn_image(src):
            stats["skipped"] += 1
            continue

        if is_http_image_url(src):
            stats["external"] += 1
            cache_key = f"remote:{html.unescape(src)}"

            if cache_key not in seen_uploads:
                print(f"      下载并上传外部图片: {src[:80]}...")
                temp_path = download_external_image(src)
                uploaded_url: Optional[str] = None
                if temp_path:
                    try:
                        uploaded_url = upload_inline_image(access_token, temp_path)
                    finally:
                        if os.path.exists(temp_path):
                            os.unlink(temp_path)
                seen_uploads[cache_key] = uploaded_url

            uploaded_url = seen_uploads[cache_key]
            if uploaded_url:
                image_tag["src"] = uploaded_url
                stats["uploaded"] += 1
            else:
                stats["failed"] += 1
            continue

        local_path = resolve_local_image_path(src, source_dir)
        if not local_path:
            continue
        if not os.path.exists(local_path):
            print(f"      正文图片不存在: {local_path}")
            stats["failed"] += 1
            continue

        stats["local"] += 1
        cache_key = f"local:{local_path}"
        if cache_key not in seen_uploads:
            print(f"      上传正文图片: {local_path}")
            seen_uploads[cache_key] = upload_inline_image(access_token, local_path)

        uploaded_url = seen_uploads[cache_key]
        if uploaded_url:
            image_tag["src"] = uploaded_url
            stats["uploaded"] += 1
        else:
            stats["failed"] += 1

    return str(soup), stats


def load_content(args: argparse.Namespace) -> Tuple[str, str, str]:
    """从 --content 或 --content-file 加载内容，返回 raw/source_dir/content_format。"""
    raw: Optional[str] = None
    source_path: Optional[str] = None

    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as handle:
            raw = handle.read()
        source_path = os.path.abspath(args.content_file)
    elif args.content is not None:
        raw = args.content
    else:
        raise ValueError("必须提供 --content 或 --content-file 之一")

    if raw is None:
        raise ValueError("内容为空")

    if args.content_format == "auto":
        if source_path and source_path.lower().endswith((".md", ".markdown")):
            content_format = "markdown"
        else:
            content_format = "html"
    else:
        content_format = args.content_format

    source_dir = os.path.dirname(source_path) if source_path else os.getcwd()
    return raw, source_dir, content_format


def prepare_content(args: argparse.Namespace, access_token: str) -> str:
    raw_content, source_dir, content_format = load_content(args)

    style_preset = args.style_preset
    if style_preset == "auto":
        tags = extract_frontmatter_tags(raw_content) if content_format == "markdown" else []
        style_preset = infer_style(raw_content, title=args.title or "", tags=tags)
        print(f"      自动推断样式: {style_preset}（基于内容分析和标签推断）")

    fragment_html = markdown_to_html(raw_content) if content_format == "markdown" else strip_full_document(raw_content)
    fragment_html, image_stats = rewrite_inline_images(fragment_html, access_token, source_dir)
    if image_stats["total"]:
        print(
            "      图片处理完成: "
            f"总计 {image_stats['total']}，"
            f"本地 {image_stats['local']}，"
            f"外部 {image_stats['external']}，"
            f"跳过 {image_stats['skipped']}，"
            f"成功 {image_stats['uploaded']}，"
            f"失败 {image_stats['failed']}"
        )
    else:
        print("      未发现需要处理的正文图片")
    extra_css = load_extra_css(args.extra_css_file)
    return build_styled_fragment(fragment_html, style_preset, extra_css)


def add_draft(access_token: str, article: dict) -> str:
    """调用草稿箱接口，返回 media_id。"""
    url = f"{WECHAT_API_BASE}/cgi-bin/draft/add"
    payload = {"articles": [article]}
    # 必须使用 ensure_ascii=False，否则中文会被转义为 \uXXXX，
    # 微信侧可能因此错误计算标题长度。
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    resp = requests.post(
        url,
        params={"access_token": access_token},
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(
            f"新增草稿失败: errcode={data.get('errcode')}, "
            f"errmsg={data.get('errmsg')}"
        )
    return data["media_id"]


def main():
    parser = argparse.ArgumentParser(description="发布文章到微信公众号草稿箱")
    parser.add_argument(
        "--appid",
        default=os.environ.get("WECHAT_APP_ID"),
        help="AppID (或设置环境变量 WECHAT_APP_ID，或在 .env 中配置)",
    )
    parser.add_argument(
        "--secret",
        default=os.environ.get("WECHAT_APP_SECRET"),
        help="AppSecret (或设置环境变量 WECHAT_APP_SECRET，或在 .env 中配置)",
    )
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--content", default=None, help="文章内容字符串（HTML 或 Markdown，与 --content-file 二选一）")
    parser.add_argument("--content-file", default=None, help="文章内容文件路径（.html 或 .md）")
    parser.add_argument("--content-format", choices=("auto", "markdown", "html"), default="auto", help="内容格式，默认自动识别")
    parser.add_argument(
        "--style-preset",
        choices=[*STYLE_NAMES, "wechat"],
        default="auto",
        help="内联样式预设: auto(自动推断) | default(通用) | code(代码密集) | essay(散文) | guide(教程) | none(无样式)，默认 auto",
    )
    parser.add_argument("--extra-css-file", default=None, help="附加 CSS 文件，会继续内联到最终 HTML 中")
    parser.add_argument("--author", default="", help="作者名（可选）")
    parser.add_argument("--digest", default="", help="摘要，最多 120 字（可选）")
    parser.add_argument("--cover-image", default=None, help="封面图片本地路径（可选）")
    parser.add_argument("--thumb-media-id", default=None, help="已有封面图片 media_id（与 --cover-image 二选一）")
    parser.add_argument("--content-source-url", default="", help="原文链接（可选）")
    args = parser.parse_args()

    if not args.appid:
        parser.error("缺少 AppID：请通过 --appid 传入、设置环境变量 WECHAT_APP_ID，或在 .env 中配置")
    if not args.secret:
        parser.error("缺少 AppSecret：请通过 --secret 传入、设置环境变量 WECHAT_APP_SECRET，或在 .env 中配置")

    print("[1/4] 获取 access_token ...")
    token = get_access_token(args.appid, args.secret)
    print("      access_token 已获取（已隐藏）")

    thumb_media_id = args.thumb_media_id
    if args.cover_image and not thumb_media_id:
        print(f"[2/4] 上传封面图片: {args.cover_image} ...")
        thumb_media_id = upload_cover_image(token, args.cover_image)
        if thumb_media_id:
            print(f"      thumb_media_id: {thumb_media_id}")
        else:
            print("      封面图片上传失败，将继续使用已有参数创建草稿")
    else:
        print("[2/4] 跳过封面图片上传")

    print("[3/4] 准备文章内容 ...")
    html_content = prepare_content(args, token)

    article = {
        "title": args.title,
        "content": html_content,
        "author": args.author,
        "digest": args.digest[:120] if args.digest else "",
        "content_source_url": args.content_source_url,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    print("[4/4] 提交草稿到微信公众号草稿箱 ...")
    media_id = add_draft(token, article)

    result = {
        "success": True,
        "media_id": media_id,
        "title": args.title,
        "message": "草稿已成功添加到草稿箱，请登录微信公众平台后台进行最终审核和发布。",
    }
    print("\n发布成功")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    main()
