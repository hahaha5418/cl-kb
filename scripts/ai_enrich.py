#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 辅助脚本（可选功能）
------------------------------------------------------------
三种能力：
  news    给自动抓取的热点写中文标题、中文摘要、打标签
  article 把热点升级成「站内可读」的富文本正文（封面+要点+高亮，不跳外网）
  polish  对已生成的正文做确定性润色（加粗关键数据/品牌，把「我」改成「你」）
  tasks   生成「今日学习任务」页面，AI 会给一句开场建议
  notes   给没有标签的笔记自动分类、打标签、写一句话总结

重要：没配置 API Key 时脚本会优雅降级——
  · news / notes 直接跳过（内容原样保留）
  · tasks 照常生成，只是没有 AI 那句建议
所以这个功能是「锦上添花」，不是必需品。

用法：
  python scripts/ai_enrich.py news|articles|polish|tasks|notes|all
  python scripts/ai_enrich.py check      测试 API 是否连通
  python scripts/ai_enrich.py news --force   已处理过的也重跑
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
NEWS_DIR = DOCS / "news"
NOTES_DIR = DOCS / "notes"
PATH_DIR = DOCS / "path"
CONFIG_FILE = ROOT / "scripts" / "ai_config.json"
TODAY_FILE = DOCS / "today.md"

CST = timezone(timedelta(hours=8))


# ---------------- Markdown frontmatter 读写 ----------------

def _unquote(v):
    """只剥掉最外面一对引号，并把 \\" 还原成 "（不能用 strip('\"')，会吃掉多余字符）"""
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1].replace('\\"', '"')
    return v


def split_md(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?", raw)
    fm = {}
    if not m:
        return fm, raw
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            v = _unquote(v)
            fm[k.strip()] = True if v == "true" else (False if v == "false" else v)
    return fm, raw[m.end():]


def dump_md(fm, body):
    """用 json.dumps 生成带引号的值，标题里有引号也不会写出坏 YAML"""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {json.dumps(str(v), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


# ---------------- 调用大模型 ----------------

class AI:
    def __init__(self, cfg):
        self.cfg = cfg
        self.key = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("AI_API_KEY")
            or cfg.get("api_key")
            or ""
        )
        base = (cfg.get("base_url") or "").lower()
        self.local = ("localhost" in base) or ("127.0.0.1" in base)
        # 本地模型（如 Ollama）不需要 Key；云端模型必须有 Key
        self.enabled = bool(cfg.get("enabled", True)) and (bool(self.key) or self.local)

    def call(self, prompt, system="你是一个简洁、准确的中文助手。", max_tokens=None):
        if not self.enabled:
            return None
        url = self.cfg["base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": self.cfg["model"],
            "temperature": self.cfg.get("temperature", 0.3),
            "max_tokens": max_tokens or self.cfg.get("max_tokens", 1500),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"    [AI 调用失败] {type(e).__name__}: {e}")
            return None

    def json(self, prompt, system="你是一个简洁、准确的中文助手。只输出 JSON。", max_tokens=None):
        text = self.call(prompt, system, max_tokens=max_tokens)
        if not text:
            return None
        t = text.strip()
        t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
        try:
            return json.loads(t)
        except Exception:
            pass
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", t)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        print("    [解析失败] 模型返回的不是合法 JSON")
        return None


# ---------------- 模式一：热点中文化 + 打标签 ----------------

def mode_news(ai, cfg, force=False):
    files = [p for p in sorted(NEWS_DIR.glob("*.md")) if p.name != "index.md"]
    todo = []
    for p in files:
        fm, body = split_md(p)
        if not fm.get("auto"):
            continue
        has_ai = bool(fm.get("ai")) and not force
        has_tip = bool(fm.get("tip")) and not force
        if has_ai and has_tip:
            continue
        # need_translate / need_tip
        todo.append((p, fm, body, not has_ai, not has_tip))

    if not todo:
        print("  没有需要处理的热点")
        return
    if not ai.enabled:
        print(f"  有 {len(todo)} 条热点待处理，但没配 API Key，跳过")
        return

    print(f"  待处理 {len(todo)} 条热点")
    size = max(1, int(cfg.get("batch_size", 5)))
    done = 0

    for i in range(0, len(todo), size):
        batch = todo[i:i + size]
        need_t = [b for b in batch if b[3]]
        need_p = [b for b in batch if b[4] and not b[3]]

        # —— 1) 需要翻译的：译中文 + 生成初学者建议 ——
        if need_t:
            listing = "\n".join(
                f'{j}. 标题：{fm.get("title", "")}\n   摘要：{fm.get("summary", "") or _plain(body)[:160]}'
                for j, (_, fm, body, _, _) in enumerate(need_t)
            )
            prompt = f"""把下面这些英文 AI 新闻改写成中文，方便中文读者快速判断值不值得点开。

对每一条输出：
- title：25 字以内的中文标题，要具体（说清是谁、干了什么），不要"某某发布新模型"这种空话
- summary：70 字以内的中文摘要，说清「发生了什么」和「为什么值得关注」
- tags：1-3 个标签，优先从这些里选：OpenAI、Claude、Gemini、国产模型、开源、视频生成、图像生成、编程开发、Agent、硬件、行业动态、研究进展、产品发布；都不合适就自拟
- tip：30 字以内，给「完全不懂 AI 的初学者」的一句话建议，要具体可操作（比如「先去术语词典查 XXX」「可以试试用 XXX 工具」）

只输出 JSON 数组，不要任何解释：
[{{"i": 0, "title": "...", "summary": "...", "tags": ["...", "..."], "tip": "..."}}]

新闻列表：
{listing}"""

            result = ai.json(prompt)
            time.sleep(float(cfg.get("sleep_seconds", 1)))
            if isinstance(result, list):
                for item in result:
                    try:
                        idx = int(item.get("i"))
                        one = need_t[idx]
                    except Exception:
                        continue
                    p, fm, body, _, _ = one
                    title_zh = str(item.get("title", "")).strip()
                    summary_zh = str(item.get("summary", "")).strip()
                    tags = item.get("tags") or []
                    if isinstance(tags, str):
                        tags = [t.strip() for t in re.split(r"[,，、\s]+", tags) if t.strip()]
                    tip = str(item.get("tip", "")).strip()
                    if not title_zh:
                        continue

                    fm["title_en"] = fm.get("title", "")
                    fm["title"] = title_zh
                    if summary_zh:
                        fm["summary_zh"] = summary_zh
                    if tags:
                        fm["tags"] = "、".join(str(t) for t in tags)
                    fm["ai"] = True
                    if tip:
                        fm["tip"] = tip

                    fm["updated"] = fm.get("updated") or iso_now()
                    # 站内阅读版正文（不再输出 [阅读原文] 跳转）
                    p.write_text(
                        dump_md(fm, render_article(fm, path=p, lead=summary_zh or None, tip=tip)),
                        encoding="utf-8", newline="\n")
                    done += 1
                    print(f"    ✓ {title_zh[:34]}")

        # —— 2) 只缺建议的：轻量补一句 tip，不重翻标题 ——
        if need_p:
            listing = "\n".join(
                f'{j}. 标题：{fm.get("title", "")}\n   摘要：{_plain(body)[:160]}'
                for j, (_, fm, body, _, _) in enumerate(need_p)
            )
            prompt = f"""给下面这些中文 AI 新闻，各写一句「初学者建议」（30 字以内），
告诉完全不懂 AI 的人可以怎么理解或动手试试，要具体可操作
（比如「先去术语词典查 XXX」「可以试试用 XXX 工具」）。

只输出 JSON 数组，不要任何解释：
[{{"i": 0, "tip": "..."}}]

新闻列表：
{listing}"""

            result = ai.json(prompt)
            time.sleep(float(cfg.get("sleep_seconds", 1)))
            if isinstance(result, list):
                for item in result:
                    try:
                        idx = int(item.get("i"))
                        one = need_p[idx]
                    except Exception:
                        continue
                    p, fm, body, _, _ = one
                    tip = str(item.get("tip", "")).strip()
                    if not tip:
                        continue
                    fm["tip"] = tip
                    fm["updated"] = fm.get("updated") or item_ts(fm, p)
                    p.write_text(
                        dump_md(fm, render_article(fm, path=p, tip=tip)),
                        encoding="utf-8", newline="\n")
                    done += 1
                    print(f"    ✓ 补建议：{fm.get('title', '')[:30]}")

    print(f"  完成，共改写 {done} 条")


def _plain(body):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|[#>*`\[\]]", " ", body)).strip()


# ============ 站内文章渲染（不再跳外网） ============
# 设计目标：点开热点就能在站内读完中文摘要，不用访问原文网站。
# 因此正文改为「封面 + 时间徽章 + 加粗高亮要点 + AI 总结 + 影响 + 建议」，
# 原来的 [阅读原文](url) 跳转删除，原始出处只在折叠块里以纯文本保留。

COVER_KEYS = ["llm", "chip", "robot", "agent", "code", "video",
              "image", "opensource", "policy", "research", "default"]

# (命中关键词, 封面 key) —— 按顺序匹配，越靠前优先级越高
COVER_RULES = [
    (("视频", "video", "sora", "动画"), "video"),
    (("图像", "绘图", "画图", "生图", "image", "图片"), "image"),
    (("机器人", "具身", "robot", "人形"), "robot"),
    (("芯片", "算力", "硬件", "gpu", "显卡", "nvidia", "英伟达"), "chip"),
    (("agent", "智能体", "助手", "自动化"), "agent"),
    (("编程", "代码", "开发", "coding", "ide", "copilot", "编码"), "code"),
    (("开源", "open source", "open-source", "github"), "opensource"),
    (("研究", "论文", "research", "学术", "算法"), "research"),
    (("政策", "监管", "法案", "合规", "安全", "行业", "融资", "收购"), "policy"),
    (("大模型", "模型", "gpt", "claude", "gemini", "llm", "qwen", "通义", "文心"), "llm"),
]


# 需要加粗的关键数据（必须带单位，避免把年份 2026 也加粗）
BOLD_DATA_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:倍|%|％|亿|万|千|B\b|M\b|K\b|GB|TB|TOPS|参数|美元|元|个|名|家))")

BRANDS = [
    "OpenAI", "Google DeepMind", "DeepMind", "Google", "Meta", "Microsoft", "微软",
    "Anthropic", "NVIDIA", "英伟达", "Amazon", "AWS", "阿里云", "阿里", "腾讯",
    "字节跳动", "百度", "华为", "苹果", "Apple", "GitHub", "Hugging Face",
    "Claude", "Gemini", "GPT", "Qwen", "通义千问", "文心", "智谱", "Kimi",
    "DeepSeek", "Copilot", "Sora", "Midjourney", "Stable Diffusion",
]


def highlight_key(text):
    """把关键数据和品牌名加粗高亮（已经加粗的片段保持原样，不重复加）"""
    if not text:
        return text
    out = []
    for seg in re.split(r"(\*\*[^*]+\*\*)", text):
        if seg.startswith("**"):
            out.append(seg)
            continue
        for b in BRANDS:
            seg = re.sub(rf"(?<!\*)({re.escape(b)})(?!\*)", r"**\1**", seg)
        seg = BOLD_DATA_RE.sub(lambda m: f"**{m.group(1)}**", seg)
        out.append(seg)
    return "".join(out)


def humanize_impact(text):
    """影响段是写给读者看的，把模型的『我』改成『你』"""
    pairs = [("我需要", "你可以"), ("我应该", "你可以"), ("我可以", "你可以"),
             ("我要", "你可以"), ("我的", "你的"), ("让我", "让你"), ("对我", "对你")]
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def pick_cover(fm):
    """按标签 / 标题 / 摘要猜一个最贴切的封面分类"""
    text = " ".join(
        str(fm.get(k, "")) for k in ("tags", "tag", "title", "title_en",
                                     "summary_zh", "summary", "source", "tip")
    ).lower()
    for keys, cover in COVER_RULES:
        for k in keys:
            if k.lower() in text:
                return cover
    return "default"


def iso_now():
    return datetime.now(CST).isoformat(timespec="seconds")


def item_ts(fm, path):
    """更新时间：优先用 frontmatter 的 updated，没有就用文件修改时间"""
    ts = fm.get("updated")
    if ts:
        return str(ts)
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, CST).isoformat(timespec="seconds")
    except Exception:
        return iso_now()


def rel_time(ts_str, now=None):
    """把 ISO 时间转成人话：X 分钟前 / X 小时前 / X 天前 / 具体日期"""
    now = now or datetime.now(CST)
    try:
        t = datetime.fromisoformat(str(ts_str))
    except Exception:
        return str(ts_str)[:10]
    if t.tzinfo is None:
        t = t.replace(tzinfo=CST)
    delta = (now - t).total_seconds()
    if delta < 0:
        delta = 0
    if delta < 60:
        return "刚刚更新"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前更新"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前更新"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)} 天前更新"
    return t.strftime("%Y-%m-%d")


def rel_time_from_date(date_str, now=None):
    """只有日期（没有具体时间）时的兜底"""
    now = now or datetime.now(CST)
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d").replace(tzinfo=CST)
    except Exception:
        return str(date_str)[:10]
    days = (now - d).days
    if days <= 0:
        return "今天更新"
    if days == 1:
        return "昨天更新"
    if days < 7:
        return f"{days} 天前更新"
    return str(date_str)[:10]


def render_article(fm, path=None, lead=None, points=None,
                   impact=None, tip=None, cover=None,
                   background=None, detail=None, actions=None):
    """渲染站内可读的新闻正文（Markdown + 少量 HTML），结构更丰满"""
    title = fm.get("title") or "AI 热点"
    source = fm.get("source") or "未标注"
    date = fm.get("date") or ""
    tag = fm.get("tags") or fm.get("tag") or "AI"
    title_en = fm.get("title_en") or ""
    url = fm.get("url") or ""
    tip = tip or fm.get("tip") or ""
    cover = cover or f"/covers/news/{pick_cover(fm)}.svg"
    # 写回 frontmatter，索引页要用它渲染卡片封面
    if fm.get("cover") != cover:
        fm["cover"] = cover

    # 时间徽章
    if path is not None:
        ts = item_ts(fm, path)
    else:
        ts = fm.get("updated") or iso_now()
    human = rel_time(ts) if fm.get("updated") or path is not None else rel_time_from_date(date)

    # 摘要（模型会在里面用 ** 标出关键词，不要整段加粗）
    lead = (lead or fm.get("summary_zh") or fm.get("summary") or "").strip()
    if not lead:
        lead = f"**{title}**——这条来自 {source} 的 AI 动态，正文总结正在自动生成中。"

    # 要点：AI 给了就用，没给就从摘要里拆句子兜底
    pts = [p for p in (points or []) if str(p).strip()]
    if not pts:
        sents = [s.strip() for s in re.split(r"[。；;！!]", lead) if len(s.strip()) > 8]
        pts = [f"**{s}**" if not s.startswith("**") else s for s in sents[:3]]
    if not pts:
        pts = [f"**{title}**"]

    # 阅读时长（把新增段落也算进去）
    extra_text = " ".join([str(background or ""), str(detail or ""),
                            str(impact or ""), str(actions or ""), str(tip or "")])
    words = len(lead) + sum(len(str(p)) for p in pts) + len(extra_text)
    minutes = max(1, round(words / 300) or 1)

    lines = [
        f'<img class="cl-article-cover" src="{cover}" alt="主题示意图" loading="lazy">',
        "",
        '<div class="cl-meta">',
        f'  <span class="cl-time" data-ts="{ts}">🕒 {human}</span>',
        f'  <span class="cl-meta-item">📰 {source}</span>',
        f'  <span class="cl-meta-item">🏷️ {tag}</span>',
        f'  <span class="cl-meta-item">⏱ 约 {minutes} 分钟读完</span>',
        '</div>',
        "",
        f"# {title}",
        "",
        "## 一句话看懂",
        "",
        highlight_key(lead),
        "",
        "## 核心要点",
        "",
    ]
    for i, pt in enumerate(pts, 1):
        pt = str(pt).strip()
        if "**" not in pt:
            pt = highlight_key(pt)
            if "**" not in pt:
                pt = f"**{pt}**"
        lines.append(f"{i}. {pt}")

    # 详细解读：优先用 AI 给的 background + detail，否则把摘要拆成两段
    lines += ["", "## 详细解读", ""]
    bg = str(background or "").strip()
    dt = str(detail or "").strip()
    if bg or dt:
        if bg:
            lines.append(highlight_key(bg))
            lines.append("")
        if dt:
            lines.append(highlight_key(dt))
            lines.append("")
    else:
        # 兜底：把 lead 拆成两段，避免一段到底
        half = len(lead) // 2
        split_pos = lead.rfind("。", 0, half + 50)
        if split_pos <= 0:
            split_pos = lead.rfind("，", 0, half + 30)
        if split_pos > 0:
            lines.append(highlight_key(lead[:split_pos + 1]))
            lines.append("")
            lines.append(highlight_key(lead[split_pos + 1:]))
        else:
            lines.append(highlight_key(lead))
        lines.append("")

    lines += ["## 为什么值得关注", ""]
    if impact:
        lines.append(highlight_key(humanize_impact(impact)))
    else:
        lines.append(f"这条动态来自 **{source}**，属于「{tag}」方向。保持对这类消息的关注，"
                     "能帮你判断哪些 AI 能力已经可用、哪些还只是宣传。")
    lines += [""]

    # 初学者可以怎么做
    act = str(actions or "").strip()
    if act or tip:
        lines += ["> 💡 **初学者可以怎么做**", ">"]
        if act:
            lines.append(f"> {act}")
        if tip:
            lines.append(f"> {tip}")
        lines.append("")

    lines += [
        "<details>",
        "<summary>原始出处（无需跳转外网）</summary>",
        "",
        f"- 原标题：{title_en or title}",
        f"- 来源：{source}",
        f"- 发布日期：{date}",
    ]
    if url:
        lines.append(f"- 原始链接（纯文本，不可点击）：`{url}`")
    lines += [
        "",
        "> 本页正文由 AI 在站内自动总结生成，**无需访问外网即可完整阅读**。",
        "</details>",
        "",
    ]
    return "\n".join(lines)


def mode_articles(ai, cfg, force=False):
    """给热点生成「站内可直接读」的富文本正文"""
    files = [p for p in sorted(NEWS_DIR.glob("*.md")) if p.name != "index.md"]
    todo = []
    for p in files:
        fm, body = split_md(p)
        if not force and fm.get("rich"):
            continue
        todo.append((p, fm, body))

    if not todo:
        print("  没有需要升级的热点")
        return

    print(f"  待升级 {len(todo)} 条热点")
    size = max(1, int(cfg.get("article_batch_size", 4)))
    sleep_s = float(cfg.get("sleep_seconds", 1))
    done = 0

    # 站内阅读正文需要更长输出，临时提高 token 上限
    article_max_tokens = int(cfg.get("article_max_tokens", 2500))

    for i in range(0, len(todo), size):
        batch = todo[i:i + size]
        payload = None

        if ai.enabled:
            listing = "\n".join(
                f'{j}. 标题：{fm.get("title", "")}\n'
                f'   来源：{fm.get("source", "")}\n'
                f'   已有摘要：{(fm.get("summary_zh") or fm.get("summary") or "")[:200]}'
                for j, (_, fm, _) in enumerate(batch)
            )
            prompt = f"""下面是一些 AI 领域的新闻条目。请把每一条改写成中文读者能**直接在站内读完**的简讯。
目标：一个完全不懂 AI 的人读完，也能明白发生了什么、为什么值得关心、可以怎么用。

写作前提：
- 你**看不到原文全文**，只能依据「标题 + 来源 + 已有摘要 + 你自己的知识」来写。
- 严禁编造具体的数字、百分比、日期、公司名、产品名。拿不准就只写定性描述。
- 如果信息确实太少，就围绕这个主题写**背景科普**：这个概念是什么、这类技术在解决什么问题、目前大致处于什么阶段。让零基础读者读完有收获，远比复述标题有价值。

对每一条输出（注意字段名必须一致）：
- lead：120-180 字的一段连贯中文，包含「发生了什么 + 相关背景 + 对普通用户的意义」。把其中 3-5 个关键词或关键数据用 **双星号** 包起来加粗。
- points：**3-4 条要点，每条必须是完整的一句话**（有主语有谓语，35-70 字），不要只写短语或标题切片。每条里用 **双星号** 标出最关键的那个词或数据。
- background：40-80 字，讲这个技术/产品/事件在解决什么问题，处于什么阶段。
- detail：60-100 字，补充 lead 没展开的因果、对比或影响。
- impact：60-100 字，具体说明「这对我（一个 AI 初学者）意味着什么」，指出该关注什么、可以拿它做什么。
- actions：40-80 字，给初学者 1-2 个具体可操作的建议（查什么词、试什么工具、关注哪个后续消息）。
- cover：从这些里选最贴切的一个：{'、'.join(COVER_KEYS)}

反面例子（不合格，只是标题切片）：
  "points": ["**GPT-6 内测曝光**", "**速度快 6 倍**"]

正面例子（合格，是完整的句子）：
  "points": ["**OpenAI 正在小范围测试新模型**，目前只向部分内测用户开放",
             "据参与者反馈 **推理速度明显快于上一代**，主要来自架构层面的优化"]

只输出 JSON 数组，不要任何解释：
[{{"i": 0, "lead": "...", "points": ["...", "..."], "background": "...", "detail": "...", "impact": "...", "actions": "...", "cover": "llm"}}]

条目列表：
{listing}"""

            payload = ai.json(prompt, max_tokens=article_max_tokens)
            time.sleep(sleep_s)

        if isinstance(payload, list):
            for item in payload:
                try:
                    one = batch[int(item.get("i"))]
                except Exception:
                    continue
                p, fm, _ = one
                cover_key = str(item.get("cover", "")).strip()
                cover = f"/covers/news/{cover_key}.svg" if cover_key in COVER_KEYS \
                    else f"/covers/news/{pick_cover(fm)}.svg"
                pts = item.get("points") or []
                if isinstance(pts, str):
                    pts = [pts]
                fm["rich"] = True
                fm["updated"] = fm.get("updated") or item_ts(fm, p)
                p.write_text(
                    dump_md(fm, render_article(
                        fm, path=p,
                        lead=str(item.get("lead", "")).strip() or None,
                        points=pts,
                        impact=str(item.get("impact", "")).strip() or None,
                        cover=cover,
                        background=str(item.get("background", "")).strip() or None,
                        detail=str(item.get("detail", "")).strip() or None,
                        actions=str(item.get("actions", "")).strip() or None,
                    )), encoding="utf-8", newline="\n")
                done += 1
                print(f"    ✓ {str(fm.get('title', ''))[:30]}")
        else:
            # AI 不可用或这批解析失败：尝试用纯文本扩写摘要；并标记 rich=false 方便下次重试
            for p, fm, _ in batch:
                expanded = None
                if ai.enabled:
                    simple_prompt = (
                        f"请把下面这条 AI 新闻扩写成一段 150-200 字的中文简讯，"
                        f"包含「发生了什么 + 相关背景 + 对初学者的意义」。"
                        f"不要编造具体数字或公司名。标题：{fm.get('title', '')}。"
                        f"已有摘要：{fm.get('summary_zh') or fm.get('summary') or ''}。"
                        f"只输出正文，不要解释。"
                    )
                    expanded = ai.call(simple_prompt, max_tokens=800)
                    time.sleep(sleep_s)
                lead = (expanded or fm.get("summary_zh") or fm.get("summary") or "").strip()
                fm["updated"] = fm.get("updated") or item_ts(fm, p)
                # 如果 AI 扩写成功，临时标记 rich=true；否则 false 方便下次重试
                fm["rich"] = bool(expanded and len(lead) > 80)
                p.write_text(
                    dump_md(fm, render_article(fm, path=p, lead=lead or None, detail=lead or None)),
                    encoding="utf-8", newline="\n")
                done += 1
                status = "（AI 扩写）" if expanded and len(lead) > 80 else "（无 AI，下次重试）"
                print(f"    · {str(fm.get('title', ''))[:30]}{status}")

    print(f"  完成，共升级 {done} 条为站内阅读版")


def mode_polish():
    """对已生成的正文做确定性润色（不调用 AI，零成本）：
    1. 关键数据 / 品牌名加粗高亮
    2. 「为什么值得关注」里模型的『我』改成『你』
    """
    files = [p for p in sorted(NEWS_DIR.glob("*.md")) if p.name != "index.md"]
    n = 0
    for p in files:
        fm, body = split_md(p)
        if not body.strip():
            continue
        # 只对正文做润色，不修改 frontmatter
        new_body = humanize_impact(body)
        # 品牌 / 数据加粗只对未加粗区域处理，避免重复
        new_body = highlight_key(new_body)
        if new_body != body:
            p.write_text(dump_md(fm, new_body), encoding="utf-8", newline="\n")
            n += 1
    print(f"  完成，共润色 {n} 条")


def mode_tasks(ai, cfg):
    """生成今日学习任务页面（docs/today.md）"""
    items = []
    if PATH_DIR.exists():
        for sd in sorted(PATH_DIR.iterdir()):
            if not sd.is_dir():
                continue
            for f in sorted(sd.glob("*.md")):
                fm, _ = split_md(f)
                if fm.get("done"):
                    continue
                items.append({
                    "title": fm.get("title") or f.stem,
                    "stage": sd.name,
                    "link": f"./path/{sd.name}/{f.name}",
                    "order": int(fm.get("order") or 999),
                })
    items.sort(key=lambda x: (x["stage"], x["order"]))
    # 按日期轮换起始位置，保证每天不重样
    start = datetime.now(CST).day % max(1, len(items)) if items else 0
    picks = []
    for j in range(min(3, len(items))):
        picks.append(items[(start + j) % len(items)])

    # 选 5 条最新热点作为推荐阅读
    news_files = sorted(NEWS_DIR.glob("*.md"))
    news_files = [p for p in news_files if p.name != "index.md"]
    recent_news = sorted(news_files, key=lambda p: p.stat().st_mtime, reverse=True)[:5]
    news_links = []
    for p in recent_news:
        fm, _ = split_md(p)
        news_links.append({
            "title": fm.get("title") or p.stem,
            "link": f"./news/{p.name}",
            "date": fm.get("date") or "",
        })

    opening = "先从建立提示词模板库开始吧，这能帮你快速上手，大概半小时就能完成。"
    if ai.enabled:
        prompt = f"""你是面向零基础用户的 AI 学习助手。今天要从学习路径里挑 3 个任务给用户做开场鼓励。
任务列表：
{chr(10).join(f"- {x['stage']} · {x['title']}" for x in picks)}

请写一段 40-70 字的开场白，亲切、口语化，告诉用户今天从哪开始、大概多久能做完。只输出这段开场白，不要标题。"""
        suggestion = ai.call(prompt)
        if suggestion:
            opening = suggestion.strip().strip('"').strip()
        time.sleep(float(cfg.get("sleep_seconds", 1)))

    today = datetime.now(CST).strftime("%Y-%m-%d")
    lines = [
        '---',
        f'title: "今日学习任务"',
        f'date: "{today}"',
        '---',
        '',
        '# 今日学习任务',
        '',
        f'> {today} · 由脚本自动生成（AI 辅助）',
        '',
        '<div class="cl-hero-grad g-today"><span class="cl-hero-icon">🎯</span><span class="cl-hero-text">今日学习任务 · 每天自动更新</span></div>',
        '',
        opening,
        '',
        '## 今天做这几件事',
        '',
    ]
    for x in picks:
        lines.append(f"1. [{x['title']}]({x['link']})　<sub>{x['stage'].replace('-', ' · ')}</sub>")
    lines += [
        '',
        '## 今天值得看的新热点',
        '',
    ]
    for x in news_links:
        lines.append(f"- [{x['title']}]({x['link']})　<sub>{x['date']}</sub>")
    lines += [
        '',
        '## 怎么打卡',
        '',
        '打开对应任务文件，把开头的 `done: false` 改成 `done: true` 并提交，',
        '[学习路径](./path/) 页面的进度条会自动更新。',
        '',
    ]
    TODAY_FILE.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"  已生成今日任务：{len(picks)} 项{'（含 AI 建议）' if ai.enabled else ''}")


def mode_notes(ai, cfg):
    """给没有标签的笔记自动分类、打标签、写一句话总结"""
    files = [p for p in sorted(NOTES_DIR.glob("*.md")) if p.name != "index.md"]
    todo = []
    for p in files:
        fm, body = split_md(p)
        # 已经自动处理过且内容没改就跳过
        if fm.get("ai") and fm.get("category") and fm.get("tags") and fm.get("summary"):
            continue
        todo.append((p, fm, body))

    if not todo:
        print("  没有需要处理的笔记")
        return

    if not ai.enabled:
        print(f"  有 {len(todo)} 篇笔记待处理，但没配 API Key，跳过")
        return

    print(f"  待处理 {len(todo)} 篇笔记")
    size = max(1, int(cfg.get("note_batch_size", 5)))
    done = 0

    for i in range(0, len(todo), size):
        batch = todo[i:i + size]
        listing = "\n".join(
            f'{j}. 标题：{fm.get("title", "")}\n   正文前 300 字：{_plain(body)[:300]}'
            for j, (_, fm, body) in enumerate(batch)
        )
        prompt = f"""给下面这些笔记自动分类、打标签、写一句话总结。

分类从这些里选：概念理解、工具实践、项目复盘、行业观察、学习路线、踩坑记录；都不合适就自拟。
标签 1-3 个，用顿号分隔。
总结 30-50 字，说清这篇笔记的核心价值。

只输出 JSON 数组，不要任何解释：
[{{"i": 0, "category": "...", "tags": "...", "summary": "..."}}]

笔记列表：
{listing}"""

        result = ai.json(prompt)
        time.sleep(float(cfg.get("sleep_seconds", 1)))
        if isinstance(result, list):
            for item in result:
                try:
                    one = batch[int(item.get("i"))]
                except Exception:
                    continue
                p, fm, body = one
                cat = str(item.get("category", "")).strip()
                tags = str(item.get("tags", "")).strip()
                summary = str(item.get("summary", "")).strip()
                if cat:
                    fm["category"] = cat
                if tags:
                    fm["tags"] = tags
                if summary:
                    fm["summary"] = summary
                fm["ai"] = True
                p.write_text(dump_md(fm, body), encoding="utf-8", newline="\n")
                done += 1
                print(f"    ✓ {fm.get('title', '')[:30]}")

    print(f"  完成，共处理 {done} 篇笔记")


def main():
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[警告] 读取 {CONFIG_FILE} 失败: {e}")

    ai = AI(cfg)

    parser = argparse.ArgumentParser(description="AI 辅助 enrich 脚本")
    parser.add_argument("mode", choices=["news", "articles", "polish", "tasks", "notes", "all", "check"])
    parser.add_argument("--force", action="store_true", help="已处理过的也重跑")
    args = parser.parse_args()

    if args.mode == "check":
        if not ai.enabled:
            print("API 未配置或 Key 缺失，AI 辅助不会启用（但脚本仍会优雅降级运行）")
            sys.exit(0)
        resp = ai.call("请只回复一个字：OK", max_tokens=10)
        print("API 连通测试结果：", resp or "无响应")
        sys.exit(0)

    if args.mode in ("news", "all"):
        print("[热点中文化]")
        mode_news(ai, cfg, force=args.force)
    if args.mode in ("articles", "all"):
        print("[热点站内阅读版]")
        mode_articles(ai, cfg, force=args.force)
    if args.mode in ("polish", "all"):
        print("[正文润色]")
        mode_polish()
    if args.mode in ("tasks", "all"):
        print("[今日学习任务]")
        mode_tasks(ai, cfg)
    if args.mode in ("notes", "all"):
        print("[笔记自动打标签]")
        mode_notes(ai, cfg)


if __name__ == "__main__":
    main()
