#!/usr/bin/env python3
"""
check-references.py - 校验文章参考链接的可访问性，失效链接提示使用 Internet Archive 存档。

用法:
  python check-references.py src/data/blog/985-when-to-use-microservices.md
  python check-references.py --skip-archive 检查后不输出 archive.org 建议

判定规则:
  [OK]       HTTP 2xx/3xx
  [DEAD]     HTTP 4xx/5xx，或明确的连接/解析失败；输出 archive.org 存档建议
  [UNKNOWN]  网络错误或超时（可能被反爬），不阻塞发布

扫描范围: Markdown 中 `## 参考` 章节内的所有链接（[label](url) 与裸 URL）。
本地相对路径与图片引用不检查。退出码: 0（无 DEAD）或 1（存在 DEAD）。
"""

import argparse
import re
import sys
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


def configure_console_encoding() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()

REFERENCE_HEADINGS = {"参考", "参考链接", "references", "reference", "related links"}
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
BARE_URL_RE = re.compile(r"(?<![\w])(https?://[^\s<>()]+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
TIMEOUT = 15


def normalize_heading(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip().lower()


def extract_reference_links(md_path: str):
    """提取参考章节内的链接列表 [(label, url)]。"""
    with open(md_path, "r", encoding="utf-8-sig") as handle:
        lines = handle.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")

    links = []
    in_reference = False
    reference_level = 0

    for line in lines:
        stripped = line.strip()
        match = HEADING_RE.match(stripped)
        if match:
            level = len(match.group(1))
            normalized = normalize_heading(match.group(2))
            if in_reference and level <= reference_level and normalized not in REFERENCE_HEADINGS:
                in_reference = False
            if normalized in REFERENCE_HEADINGS:
                in_reference = True
                reference_level = level
                continue
        if not in_reference:
            continue

        line_links = []
        for label, url in LINK_RE.findall(stripped):
            line_links.append((label, url))
            stripped = stripped.replace(url, "", 1)
        for url in BARE_URL_RE.findall(stripped):
            line_links.append((url, url))
        links.extend(line_links)

    return links


def check_url(url: str) -> tuple[str, str]:
    """返回 (状态, 详情)。状态为 OK / DEAD / UNKNOWN。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "UNKNOWN", f"非 http(s) 链接，跳过: {url[:60]}"

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        },
        method="HEAD",
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            status = response.status
            if 200 <= status < 400:
                return "OK", f"HTTP {status}"
            return "DEAD", f"HTTP {status}"
    except Exception as head_error:
        # 部分站点拒绝 HEAD，回退到 GET（只读响应头，立即关闭）
        get_request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        try:
            with urlopen(get_request, timeout=TIMEOUT) as response:
                status = response.status
                if 200 <= status < 400:
                    return "OK", f"HTTP {status}（HEAD 失败: {head_error.__class__.__name__}，GET 通过）"
                return "DEAD", f"HTTP {status}"
        except Exception:
            return "UNKNOWN", f"{head_error.__class__.__name__}: {head_error}"


def archive_url(url: str) -> str:
    return f"https://web.archive.org/web/2023/{url}"


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 Markdown 参考链接可访问性")
    parser.add_argument("markdown", help="文章 Markdown 路径")
    parser.add_argument(
        "--skip-archive",
        action="store_true",
        help="不输出 Internet Archive 存档建议",
    )
    args = parser.parse_args()

    links = extract_reference_links(args.markdown)
    if not links:
        print("未找到参考章节或链接")
        return

    results = []
    dead_count = 0
    for label, url in links:
        status, detail = check_url(url)
        if status == "DEAD":
            dead_count += 1
        results.append((label, url, status, detail))

    print(f"共 {len(links)} 个参考链接:\n")
    for label, url, status, detail in results:
        print(f"  [{status}] {url[:90]}")
        print(f"            ({detail})")
        if status == "DEAD" and not args.skip_archive:
            print(f"            → 建议: {archive_url(url)}")

    if dead_count:
        print(f"\n{dead_count} 个链接失效，建议替换为上方 archive.org 存档链接后重新校验。")
        sys.exit(1)
    print("\n所有链接可用。")


if __name__ == "__main__":
    main()
