#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具教程「步骤条 + 高亮卡」迁移脚本（零 AI 成本）
------------------------------------------------------------
把 docs/tools/*.md 里已有的教程，按现在的新版 render_tool 重新排版：
  · 新手实操 → <Steps>/<Step> 步骤条
  · 提示 / 坑 / 不适合 → <Callout> 高亮卡片
只改排版、不改文案，因此不调用任何 AI、不联网、不会 404。

用法：python scripts/migrate_tutorials.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ai_enrich import split_md, dump_md  # noqa: E402
from build_tutorials import render_tool   # noqa: E402

TOOLS = ROOT / "docs" / "tools"


def parse_sections(body):
    """按 '## 标题' 切分成 {标题: 内容} """
    sections = {}
    cur = None
    buf = []
    for line in body.split("\n"):
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if cur is not None:
                sections[cur] = "\n".join(buf).strip()
            cur = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if cur is not None:
        sections[cur] = "\n".join(buf).strip()
    return sections


def parse_list(text):
    return [re.sub(r"^[-*]\s+", "", l).strip()
            for l in text.split("\n") if re.match(r"^[-*]\s+", l)]


def parse_steps(text):
    steps = []
    for line in text.split("\n"):
        line = line.strip()
        if not re.match(r"^\d+\.\s+", line):
            continue
        body = re.sub(r"^\d+\.\s+", "", line)
        # 1) **标题**：细节
        m = re.match(r"^\*\*(.+?)\*\*\s*[:：]\s*(.+)$", body)
        if m:
            steps.append({"t": m.group(1).strip(), "d": m.group(2).strip()})
            continue
        # 2) 标题：细节（无加粗）
        m = re.match(r"^(.+?)\s*[:：]\s+(.+)$", body)
        if m:
            steps.append({"t": m.group(1).strip(), "d": m.group(2).strip()})
            continue
        # 3) 仅标题
        steps.append({"t": body.strip(), "d": ""})
    return steps


def main():
    files = [p for p in sorted(TOOLS.glob("*.md")) if p.name != "index.md"]
    done = 0
    for p in files:
        fm, body = split_md(p)
        if not fm.get("tut"):
            continue
        sec = parse_sections(body)
        d = {}

        ol = sec.get("一句话看懂", "")
        if ol:
            d["oneline"] = re.sub(r"\s+", " ", ol).strip()

        wh = sec.get("它到底是什么", "")
        if wh:
            d["what"] = wh

        uses = parse_list(sec.get("你能用它做什么", ""))
        if uses:
            d["uses"] = uses

        steps = parse_steps(sec.get("新手实操：一步一步跟着做", ""))
        if steps:
            d["steps"] = steps

        tips = parse_list(sec.get("让效果更好的小技巧", ""))
        if tips:
            d["tips"] = tips

        pits = parse_list(sec.get("新手常踩的坑", ""))
        if pits:
            d["pitfalls"] = pits

        notfor = parse_list(sec.get("它不适合什么", ""))
        if notfor:
            d["notfor"] = notfor

        new_body = render_tool(fm, d)
        p.write_text(dump_md(fm, new_body), encoding="utf-8", newline="\n")
        done += 1
        print("  ✓", fm.get("title", p.name)[:30])

    print(f"\n迁移完成：{done} 个工具教程已升级为步骤条 + 高亮卡")


if __name__ == "__main__":
    main()
