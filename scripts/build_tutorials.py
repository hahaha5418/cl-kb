#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具库 / 场景教程生成器
------------------------------------------------------------
把 docs/tools/ 下的每个工具，重写成**纯中文的站内实操教程**：
  · 不再出现任何外链跳转（官网地址只以不可点击的纯文本出现）
  · 不出现代码、命令行、配置文件
  · 有封面图、有分步骤的新手实操流程（序号 + 加粗重点）
没配 API Key 时优雅降级：用现有信息生成骨架，不影响构建。

用法：
  python scripts/build_tutorials.py            # 生成/更新工具教程
  python scripts/build_tutorials.py --force    # 已生成过的也重跑
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ai_enrich import AI, CONFIG_FILE, split_md, dump_md  # noqa: E402

TOOLS_DIR = ROOT / "docs" / "tools"

# 分类 -> 封面
CAT_COVER = {
    "对话助手": "chat",
    "编程开发": "code",
    "图像生成": "image",
    "视频生成": "video",
    "工作流自动化": "flow",
    "办公演示": "office",
    "搜索研究": "search",
}


def cover_for(cat):
    return f"/covers/news/{CAT_COVER.get(cat, 'default')}.svg"


def bold_key(text):
    """把关键数据加粗（已是 ** 的片段跳过）"""
    if not text:
        return text
    out = []
    for seg in re.split(r"(\*\*[^*]+\*\*)", text):
        if seg.startswith("**"):
            out.append(seg)
            continue
        seg = re.sub(r"(\d+(?:\.\d+)?\s*(?:倍|%|％|分钟|小时|天|页|个|条|款|元|美元))",
                     r"**\1**", seg)
        out.append(seg)
    return "".join(out)


def render_tool(fm, d):
    title = fm.get("title") or "工具"
    cat = fm.get("category") or "未分类"
    score = fm.get("score") or 0
    price = fm.get("price") or "未标注"
    url = fm.get("url") or ""
    cover = cover_for(cat)
    stars = "★" * int(score) + "☆" * (5 - int(score))

    L = [f'<img class="cl-article-cover" src="{cover}" alt="" loading="lazy">', ""]
    L += ['<div class="cl-meta">']
    L += [f'  <span class="cl-meta-item">🧰 {cat}</span>']
    L += [f'  <span class="cl-meta-item">⭐ {stars}</span>']
    L += [f'  <span class="cl-meta-item">💰 {price}</span>']
    L += ['</div>', ""]
    L += [f"# {title}", ""]

    if d.get("oneline"):
        L += ["<Callout type=\"info\" title=\"一句话看懂\">", bold_key(d["oneline"]), "</Callout>", ""]
    if d.get("what"):
        L += ["## 它到底是什么", "", bold_key(d["what"]), ""]

    uses = [u for u in (d.get("uses") or []) if str(u).strip()]
    if uses:
        L += ["## 你能用它做什么", ""]
        for u in uses:
            u = str(u).strip()
            if "**" not in u:
                u = f"**{u}**"
            L.append(f"- {u}")
        L.append("")

    steps = [s for s in (d.get("steps") or []) if isinstance(s, dict) and s.get("t")]
    if steps:
        L += ["## 新手实操：一步一步跟着做", "", "<Steps>"]
        for s in steps:
            t = str(s.get("t", "")).strip().replace('"', '&quot;')
            detail = str(s.get("d", "")).strip()
            if detail:
                L.append(f"<Step title=\"{t}\">{bold_key(detail)}</Step>")
            else:
                L.append(f"<Step title=\"{t}\"></Step>")
        L += ["</Steps>", ""]

    tips = [t for t in (d.get("tips") or []) if str(t).strip()]
    if tips:
        L += ["<Callout type=\"tip\" title=\"让效果更好的小技巧\">", ""]
        for t in tips:
            t = str(t).strip()
            if "**" not in t:
                t = f"**{t}**"
            L.append(f"- {t}")
        L += ["</Callout>", ""]

    pits = [p for p in (d.get("pitfalls") or []) if str(p).strip()]
    if pits:
        L += ["<Callout type=\"warn\" title=\"新手常踩的坑\">", ""]
        for p in pits:
            p = str(p).strip()
            if "**" not in p:
                p = f"**{p}**"
            L.append(f"- {p}")
        L += ["</Callout>", ""]

    notfor = [n for n in (d.get("notfor") or []) if str(n).strip()]
    if notfor:
        L += ["<Callout type=\"warn\" title=\"它不适合什么\">", ""]
        for n in notfor:
            L.append(f"- {str(n).strip()}")
        L += ["</Callout>", ""]

    if url:
        L += ["## 去哪里找它", "",
              f"官网地址（**请手动复制到浏览器地址栏打开**）：`{url}`", "",
              "> 本页是**站内教程**，地址被写成不可点击的纯文本——这样就不会出现点了打不开的链接。", ""]
    return "\n".join(L)


PROMPT = """你是给「完全不懂技术的中国新手」写工具教程的编辑。
下面每个 AI 工具，请写成一段站内就能读完的中文教程。

铁律：
1. **绝对不要出现代码、命令行、JSON、配置文件、变量名**。全部用大白话和中文描述。
2. 不要出现 markdown 代码块（```）。示例提示词请用中文引号「」包起来，写成普通文字。
3. 步骤必须具体到「点哪里、填什么、选哪个」，让新手能照着一步步做出来。
4. 面向国内用户：优先提国内能用、中文界面好的做法；如果工具本身在国内访问困难，请在 pitfalls 里明确说明，并推荐国内可替代的思路。
5. 关键数字、关键按钮名、关键操作用 **双星号** 加粗。

对每个工具输出：
- oneline：25 字以内一句话定位，加粗核心词
- what：80-120 字，用生活化的类比说清「它是什么、解决什么问题」
- uses：3-4 条「你能用它做什么」，每条 20-40 字的完整句子
- steps：6-8 步新手实操流程，每步 {{"t": "步骤小标题（8字内）", "d": "具体怎么做，40-70字"}}
- tips：3 条让效果更好的技巧
- pitfalls：3 条新手常踩的坑（含国内访问/收费/隐私等现实问题）
- notfor：2 条「它不适合什么」

只输出 JSON 数组，不要任何解释：
[{{"i":0,"oneline":"...","what":"...","uses":["..."],"steps":[{{"t":"...","d":"..."}}],"tips":["..."],"pitfalls":["..."],"notfor":["..."]}}]

工具列表：
{listing}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    ai = AI(cfg)
    print(f"AI 状态：{'已启用' if ai.enabled else '未启用（将生成骨架版）'}\n")

    files = [p for p in sorted(TOOLS_DIR.glob("*.md")) if p.name != "index.md"]
    todo = []
    for p in files:
        fm, body = split_md(p)
        if fm.get("tut") and not args.force:
            continue
        todo.append((p, fm))

    if not todo:
        print("  工具教程都已是最新")
        return

    print(f"  待生成 {len(todo)} 个工具教程")
    size = 4
    done = 0
    for i in range(0, len(todo), size):
        batch = todo[i:i + size]
        listing = "\n".join(
            f'{j}. 名称：{fm.get("title","")}\n   分类：{fm.get("category","")}\n'
            f'   价格：{fm.get("price","")}\n   原有简介：{str(fm.get("desc") or "")[:120]}'
            for j, (_, fm) in enumerate(batch)
        )
        data = ai.json(PROMPT.format(listing=listing)) if ai.enabled else None
        time.sleep(float(cfg.get("sleep_seconds", 1)))

        if isinstance(data, list):
            for item in data:
                try:
                    p, fm = batch[int(item.get("i"))]
                except Exception:
                    continue
                fm["tut"] = True
                fm["cover"] = cover_for(fm.get("category", ""))
                # 写进 desc，索引卡片就能显示「一句话看懂」
                if item.get("oneline"):
                    fm["desc"] = re.sub(r"\*\*", "", str(item["oneline"])).strip()
                p.write_text(dump_md(fm, render_tool(fm, item)),
                             encoding="utf-8", newline="\n")
                done += 1
                print(f"    ✓ {fm.get('title','')[:28]}")
        else:
            # 骨架版故意不写 tut 标记，下次运行会自动重试
            for p, fm in batch:
                fm.pop("tut", None)
                fm["cover"] = cover_for(fm.get("category", ""))
                p.write_text(dump_md(fm, render_tool(fm, {})),
                             encoding="utf-8", newline="\n")
                done += 1
                print(f"    · {fm.get('title','')[:28]}（骨架版，下次会重试）")

    print(f"\n  完成，共生成 {done} 个工具教程")


if __name__ == "__main__":
    main()
