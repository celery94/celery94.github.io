#!/usr/bin/env python3
"""
pick-cover-style.py - 从封面风格池随机选择 1 个风格，输出 JSON。

用法:
  python pick-cover-style.py                # 随机选择并输出 JSON
  python pick-cover-style.py --list         # 列出全部 40 项风格
  python pick-cover-style.py --seed 42      # 指定随机种子（可复现）

输出 JSON 字段:
  selected_style                     风格名称（写入 cover-brief.json）
  selected_style_prompt_descriptor   用于生图 prompt 的安全描述词
  selected_style_reason              写入 brief 的理由说明（随机选中）

风格清单与 cover-prompt-template.md 保持一致；新增风格时需同步两处。
"""

import argparse
import json
import random
import sys


def configure_console_encoding() -> None:
    """Windows 控制台优先使用 UTF-8，避免输出中文时报 cp1252 编码错误。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()

STYLE_POOL = [
    ("日漫少年风", "energetic shonen-inspired manga look, clean ink lines, dynamic poses, readable action rhythm, bright restrained color accents"),
    ("日漫少女风", "soft shojo-inspired manga look, elegant linework, expressive faces, gentle decorative details, luminous pastel accents"),
    ("青年写实风", "mature realistic comic illustration, grounded anatomy, restrained expressions, cinematic everyday lighting, detailed but readable scenes"),
    ("治愈日常风", "cozy slice-of-life illustration, warm natural light, soft domestic details, calm pacing, gentle hand-drawn texture"),
    ("热血战斗风", "high-energy battle comic look, strong silhouettes, speed lines, impact framing, bold contrast without excessive clutter"),
    ("校园恋爱风", "youthful campus romance illustration, clean school-life setting, soft backlight, subtle emotional gestures, fresh color palette"),
    ("韩漫条漫风", "polished vertical-webtoon-inspired rendering adapted to a wide cover, clean gradients, sharp character shapes, glossy color blocks"),
    ("国漫二次元风", "contemporary Chinese anime-comic illustration, crisp linework, ornate but controlled details, vibrant fantasy-tech color accents"),
    ("港漫武侠风", "bold martial-arts comic look, expressive ink strokes, dramatic stances, gritty texture, strong motion arcs"),
    ("美漫超级英雄风", "American superhero-comic energy, bold outlines, halftone texture, dramatic perspective, high-contrast color blocking"),
    ("欧漫清线风", "European clear-line comic style, precise outlines, flat readable colors, tidy environments, restrained humor and detail"),
    ("赛博朋克风", "cyberpunk comic mood, neon accents, rain-slick surfaces, dense urban tech atmosphere, controlled purple-blue usage"),
    ("蒸汽朋克风", "steampunk adventure illustration, brass mechanisms, gears, goggles, warm industrial light, handcrafted machinery"),
    ("黑暗奇幻风", "dark fantasy illustration, gothic silhouettes, ancient textures, moody rim light, restrained magical atmosphere"),
    ("科幻机甲风", "science-fiction mecha concept illustration, mechanical forms, hard-surface details, cockpit-scale cues, cool industrial palette"),
    ("水彩漫画风", "watercolor comic illustration, translucent washes, visible paper texture, soft edges, light ink structure"),
    ("厚涂插画风", "painterly digital illustration, rich brushwork, volumetric lighting, strong focal contrast, textured color masses"),
    ("极简线稿风", "minimalist line-art illustration, sparse clean strokes, ample negative space, precise symbolic objects, limited accent color"),
    ("黑白版画风", "black-and-white printmaking look, carved textures, bold shadows, high contrast, poster-like but no title text"),
    ("Q版 Chibi 风", "chibi character illustration, small cute proportions, simplified expressions, playful shapes, clear infographic readability"),
    ("美式卡通风", "American cartoon illustration, elastic shapes, clear expressions, bold color fields, light comedic timing"),
    ("吉卜力动画风", "warm hand-drawn animation feeling, natural environments, gentle fantasy everyday mood, soft painterly backgrounds, no studio imitation"),
    ("迪士尼动画风", "bright family-animation feeling, rounded character shapes, clear emotional acting, polished color and lighting, no studio imitation"),
    ("独立漫画风", "indie comic illustration, personal hand-drawn marks, muted palette, imperfect line texture, intimate editorial feeling"),
    ("像素复古风", "retro pixel-art inspired illustration, blocky forms, limited palette, old game composition cues, readable wide layout"),
    ("悬疑惊悚风", "suspense thriller comic mood, low-key lighting, sharp shadows, uneasy framing, controlled tension without gore"),
    ("废土末日风", "post-apocalyptic wasteland illustration, weathered materials, dusty atmosphere, survival objects, desaturated contrast"),
    ("洛丽塔幻想风", "ornate fantasy fashion illustration, lace-like detail, dollhouse elegance, soft magical palette, controlled decorative density"),
    ("中国古风仙侠风", "Chinese xianxia fantasy illustration, flowing robes, ink-wash atmosphere, mountains and clouds, elegant magical motion"),
    ("新海诚光影风", "transparent blue skies, dramatic backlight, detailed clouds, youthful cinematic lighting, rain and reflection details, no artist imitation"),
    ("高对比电影风", "high-contrast cinematic illustration, strong key light, deep shadows, wide-screen composition, dramatic but realistic color grading"),
    ("涂鸦街头风", "street-graffiti comic style, spray-paint texture, bold outlines, urban wall energy, vivid but controlled color clashes"),
    ("低饱和文艺风", "low-saturation arthouse illustration, quiet composition, subtle grain, muted colors, reflective emotional tone"),
    ("90年代复古动画风", "1990s retro animation look, cel-shaded color, analog grain, bold simple backgrounds, nostalgic broadcast texture"),
    ("游戏原画风", "game concept art illustration, clear hero object, readable environment storytelling, polished lighting, production-art detail"),
    ("动态分镜电影风", "dynamic cinematic storyboard style, sequential panels, camera-motion feeling, strong cuts, clear narrative beats"),
    ("手绘铅笔草稿风", "hand-drawn pencil sketch look, visible construction lines, graphite texture, loose but intentional composition"),
    ("彩铅绘本风", "colored-pencil picture-book illustration, tactile strokes, gentle palette, warm narrative objects, soft educational tone"),
    ("儿童童话风", "children's fairy-tale illustration, simple magical forms, friendly proportions, bright storybook palette, safe wonder"),
    ("暗黑哥特风", "dark gothic illustration, pointed arches, lace shadows, candlelit contrast, ornate black shapes, restrained horror mood"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="从封面风格池随机选择 1 个风格")
    parser.add_argument("--list", action="store_true", help="列出全部风格池")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（可复现选择）")
    args = parser.parse_args()

    if args.list:
        for index, (name, _descriptor) in enumerate(STYLE_POOL, start=1):
            print(f"{index:>2}. {name}")
        return

    if args.seed is not None:
        random.seed(args.seed)
    name, descriptor = random.choice(STYLE_POOL)

    result = {
        "selected_style": name,
        "selected_style_prompt_descriptor": descriptor,
        "selected_style_reason": "用户未指定风格，本篇从风格池随机选中",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
