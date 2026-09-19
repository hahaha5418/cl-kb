#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成热点文章用的主题封面图（纯本地 SVG，零网络依赖）
------------------------------------------------------------
为什么不用外链图库：用户的网络环境访问不了 Unsplash / picsum 等境外图床，
外链图片会大面积裂图。这里用 Python 直接画出 SVG 占位封面，
体积小、必能加载、风格统一（蓝紫科技风，和整站一致）。

用法：
  python scripts/gen_covers.py
产出：
  docs/public/covers/news/<key>.svg
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "public" / "covers" / "news"

W, H = 1200, 630

# key -> (主色, 副色, 中文标签, 英文小字)
THEMES = {
    "llm":        ("#6d28d9", "#2563eb", "大模型", "Large Language Model"),
    "chip":       ("#0891b2", "#0e7490", "AI 芯片", "AI Chip & Hardware"),
    "robot":      ("#ea580c", "#c2410c", "机器人", "Robotics"),
    "agent":      ("#4f46e5", "#7c3aed", "AI Agent", "Autonomous Agent"),
    "code":       ("#059669", "#047857", "编程开发", "AI Coding"),
    "video":      ("#db2777", "#be185d", "视频生成", "Video Generation"),
    "image":      ("#c026d3", "#7e22ce", "图像生成", "Image Generation"),
    "opensource": ("#1d4ed8", "#4338ca", "开源生态", "Open Source"),
    "policy":     ("#475569", "#334155", "行业动态", "Industry & Policy"),
    "research":   ("#0d9488", "#0f766e", "研究进展", "Research"),
    "office":     ("#0ea5e9", "#2563eb", "办公演示", "Office & Slides"),
    "chat":       ("#7c3aed", "#4f46e5", "对话助手", "AI Chat Assistant"),
    "search":     ("#14b8a6", "#0d9488", "搜索研究", "Search & Research"),
    "flow":       ("#6366f1", "#4338ca", "工作流自动化", "Workflow Automation"),
    "default":    ("#4f46e5", "#7c3aed", "AI 热点", "AI Daily"),
}


def svg(key, c1, c2, label, en):
    gid = f"g{re.sub(r'[^a-z]', '', key)}"
    # 装饰：网格线
    grid = "".join(
        f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="#fff" stroke-opacity="0.05" stroke-width="1"/>'
        for x in range(0, W + 1, 60)
    ) + "".join(
        f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="#fff" stroke-opacity="0.05" stroke-width="1"/>'
        for y in range(0, H + 1, 60)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <radialGradient id="{gid}r" cx="78%" cy="22%" r="60%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.30"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#{gid})"/>
  {grid}
  <rect width="{W}" height="{H}" fill="url(#{gid}r)"/>

  <!-- 装饰光晕圆 -->
  <circle cx="1010" cy="130" r="170" fill="#fff" fill-opacity="0.07"/>
  <circle cx="1010" cy="130" r="260" fill="none" stroke="#fff" stroke-opacity="0.13" stroke-width="2"/>
  <circle cx="140" cy="540" r="120" fill="#fff" fill-opacity="0.06"/>
  <circle cx="140" cy="540" r="200" fill="none" stroke="#fff" stroke-opacity="0.10" stroke-width="2"/>

  <!-- 左侧高亮竖条 -->
  <rect x="72" y="212" width="8" height="150" rx="4" fill="#fff" fill-opacity="0.85"/>

  <!-- 中文主标题 -->
  <text x="108" y="300" font-family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"
        font-size="86" font-weight="800" fill="#ffffff" letter-spacing="2">{label}</text>

  <!-- 英文副标题 -->
  <text x="112" y="356" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="30" font-weight="500" fill="#ffffff" fill-opacity="0.78" letter-spacing="6">{en}</text>

  <!-- 底部标签 -->
  <rect x="108" y="410" width="176" height="44" rx="22" fill="#ffffff" fill-opacity="0.16"/>
  <text x="196" y="439" text-anchor="middle" font-family="PingFang SC, Microsoft YaHei, sans-serif"
        font-size="22" font-weight="600" fill="#ffffff">CL AI 知识库</text>
</svg>
'''


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for key, (c1, c2, label, en) in THEMES.items():
        (OUT_DIR / f"{key}.svg").write_text(svg(key, c1, c2, label, en), encoding="utf-8")
        print(f"  ✓ covers/news/{key}.svg  （{label}）")
    print(f"\n共生成 {len(THEMES)} 张封面 → {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
