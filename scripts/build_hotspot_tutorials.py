#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点实操教程生成器（hotspot → 可照做的 5 步指南）
------------------------------------------------------------
把「每日热点」里反复出现的话题（AI 做视频 / 写代码 / 搭 Agent …），
自动转化成一篇**能照着做的实操教程**，落盘到 docs/scenes/hot-<slug>.md，
由 build-content.mjs 自动收进「场景应用」索引与侧边栏。

和 build_tutorials.py 的分工：
  · build_tutorials.py  —— 以**工具**为线索（工具库某个工具怎么用），内容常青
  · 本脚本             —— 以**当下热点**为线索（最近大家都在聊什么、现在该动手做什么），
                          不含日期就不会重复，每跑一次都自带最新的「为什么现在值得学」

设计原则：
  1. 零硬依赖：没有 API Key 时生成**骨架版**（照样能读、能照着做），不阻塞流水线
  2. 失败静默：任何异常都不抛出，只跳过该话题，绝不让 07:00 的自动化卡死
  3. 幂等：同文件路径稳定，每跑一次覆盖更新；骨架版故意不写 hot 标记，
     下次有 Key 时自动升级成 AI 版

用法：
  python scripts/build_hotspot_tutorials.py                # 生成/更新
  python scripts/build_hotspot_tutorials.py --force        # 已生成的也重跑
  python scripts/build_hotspot_tutorials.py --max-topics 3 # 只处理前 3 个话题
  python scripts/build_hotspot_tutorials.py --dry-run      # 只看命中统计，不写文件
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ai_enrich import AI, CONFIG_FILE, split_md, dump_md  # noqa: E402

NEWS_DIR = ROOT / "data" / "news"
SCENES_DIR = ROOT / "docs" / "scenes"

# ---------- 话题规则表 ----------
# signals：命中热点标题 / 摘要 / 标签 / 实体里任意一个词，就算属于该话题
# tools_hint：给模型和白话骨架用的「现在主流可行的工具方向」（不写死具体产品功能，避免瞎编）
TOPICS = [
    {
        "slug": "ai-video",
        "title": "用 AI 做一条视频",
        "emoji": "🎬",
        "cover": "/covers/news/video.svg",
        "tools": "可灵 / 即梦 / 海螺 / 剪映（免费额度够新手试）",
        "signals": ["视频", "文生视频", "视频生成", "可灵", "即梦", "sora", "veo", "runway",
                    "剪辑", "配音", "数字人", "口播", "video"],
    },
    {
        "slug": "ai-code",
        "title": "让 AI 帮你写代码",
        "emoji": "💻",
        "cover": "/covers/news/code.svg",
        "tools": "Cursor / GitHub Copilot / Trae / 通义灵码（先挑一个，别贪多）",
        "signals": ["代码", "编程", "copilot", "cursor", "codex", "claude code", "trae",
                    "灵码", "程序", "脚本", "ide", "code", "coding"],
    },
    {
        "slug": "ai-agent",
        "title": "搭一个自己的 AI 助手（Agent）",
        "emoji": "🤖",
        "cover": "/covers/news/chat.svg",
        "tools": "扣子 Coze / Dify / n8n（低代码，不用写代码也能起步）",
        "signals": ["agent", "智能体", "智能代理", "mcp", "工具调用", "function calling",
                    "多智能体", "工作流", "自动化"],
    },
    {
        "slug": "ai-image",
        "title": "用 AI 出图 / 做配图",
        "emoji": "🎨",
        "cover": "/covers/news/image.svg",
        "tools": "即梦 / 通义万相 / 豆包（国内直接可用，中文提示词友好）",
        "signals": ["图像", "绘画", "配图", "文生图", "生图", "出图", "midjourney",
                    "stable diffusion", "nano banana", "flux", "修图", "image"],
    },
    {
        "slug": "ai-office",
        "title": "用 AI 做 PPT 和表格",
        "emoji": "📊",
        "cover": "/covers/news/office.svg",
        "tools": "Gamma / Kimi / WPS AI / 讯飞智文（先把手头那份文档丢进去试）",
        "signals": ["ppt", "excel", "表格", "办公", "文档", "gamma", "wps", "汇报",
                    "纪要", "会议", "office"],
    },
    {
        "slug": "ai-local-model",
        "title": "在自己电脑上跑大模型",
        "emoji": "🖥️",
        "cover": "/covers/news/opensource.svg",
        "tools": "Ollama / LM Studio + 开源模型（先看显存，再挑模型大小）",
        "signals": ["本地部署", "本地", "ollama", "lm studio", "私有化", "量化", "显存",
                    "开源模型", "开源", "llama", "qwen", "推理"],
    },
    {
        "slug": "ai-search",
        "title": "用 AI 搜索查资料（不瞎编的那种）",
        "emoji": "🔍",
        "cover": "/covers/news/search.svg",
        "tools": "秘塔 AI 搜索 / Perplexity / Kimi（联网版）（关键：让它给出来源）",
        "signals": ["搜索", "search", "perplexity", "秘塔", "联网", "检索", "rag",
                    "知识库问答", "信源", "幻觉", "查证"],
    },
    {
        "slug": "ai-writing",
        "title": "用 AI 写文章 / 做自媒体",
        "emoji": "✍️",
        "cover": "/covers/news/write.svg",
        "tools": "Kimi / 豆包 / DeepSeek（先喂素材再让它写，别直接让它编）",
        "signals": ["写作", "公众号", "文案", "自媒体", "小红书", "头条", "标题",
                    "写作助手", "content", "写作工具", "润色"],
    },
    {
        "slug": "ai-english",
        "title": "用 AI 学英语 / 练口语",
        "emoji": "🗣️",
        "cover": "/covers/news/edu.svg",
        "tools": "豆包 / 多邻国 AI / Kimi（语音对话功能直接当陪练）",
        "signals": ["英语", "翻译", "口语", "外语", "学习语言", "雅思", "托福",
                    "translation", "听力", "陪练", "双语", "语言学习", "多语",
                    "语音对话", "语音助手", "stepaudio", "语音交互", "对话式", "realtime 语音"],
    },
    {
        "slug": "ai-audio",
        "title": "用 AI 做播客 / 配音 / 数字人语音",
        "emoji": "🎙️",
        "cover": "/covers/news/audio.svg",
        "tools": "豆包语音 / 海螺语音 / 剪映朗读（文字转语音三分钟上手）",
        "signals": ["语音", "配音", "tts", "播客", "podcast", "音频", "朗读",
                    "speech", "声音克隆", "voice", "口播"],
    },
    {
        "slug": "ai-music",
        "title": "用 AI 写歌 / 做背景音乐",
        "emoji": "🎵",
        "cover": "/covers/news/music.svg",
        "tools": "Suno / 天工 SkyMusic（写好歌词再让它唱）",
        "signals": ["音乐", "歌曲", "suno", "写歌", "作词", "作曲", "music",
                    "旋律", "编曲"],
    },
    {
        "slug": "ai-notes",
        "title": "搭一个自己的 AI 知识库 / 笔记",
        "emoji": "📚",
        "cover": "/covers/news/knowledge.svg",
        "tools": "Obsidian + AI 插件 / flomo / NotebookLM（先把笔记攒起来再谈 AI）",
        "signals": ["知识库", "笔记", "obsidian", "notebooklm", "记忆", "备忘",
                    "note", "第二大脑", "收藏", "整理"],
    },
    {
        "slug": "ai-data",
        "title": "用 AI 做数据分析 / 出图表",
        "emoji": "📈",
        "cover": "/covers/news/data.svg",
        "tools": "Kimi / 豆包 / WPS AI（把表格文件直接丢进去提问）",
        "signals": ["数据分析", "图表", "报表", "统计", "bi", "数据可视化",
                    "sql", "数据清洗", "csv", "透视表"],
    },
    {
        "slug": "ai-writing",
        "title": "用 AI 写文章 / 做自媒体",
        "emoji": "✍️",
        "cover": "/covers/news/write.svg",
        "tools": "Kimi / 豆包 / DeepSeek（先喂素材再让它写，别直接让它编）",
        "signals": ["写作", "公众号", "文案", "自媒体", "小红书", "头条", "标题",
                    "写作助手", "润色", "创作", "博客", "blog", "稿件"],
    },
    {
        "slug": "ai-fraud",
        "title": "用 AI 防诈骗 / 识破深度伪造",
        "emoji": "🛡️",
        "cover": "/covers/news/shield.svg",
        "tools": "自己的眼睛 + 豆包 / Kimi（多问一句、交叉核验就是最好的工具）",
        "signals": ["诈骗", "欺诈", "深度伪造", "deepfake", "换脸", "仿冒", "钓鱼",
                    "phishing", "隐私", "辟谣", "谣言", "声音克隆"],
    },
    {
        "slug": "ai-opensource",
        "title": "上手一个开源 AI 项目",
        "emoji": "🧩",
        "cover": "/covers/news/opensource.svg",
        "tools": "Hugging Face / GitHub + Ollama（从「能一键跑起来」的项目开始）",
        "signals": ["开源", "github", "open source", "开源项目", "hugging face",
                    "模型权重", "部署"],
    },
]

MIN_ITEMS = 3          # 命中热点少于这个数就跳过该话题（凑不够素材，写出来也是空话）
RECENT_DAYS = 21       # 只取最近这些天的热点
MAX_NEWS_PER_TOPIC = 8 # 喂给模型的素材上限
_CJK = re.compile(r"[\u4e00-\u9fff]")

# 送给大模型前的**内容安全过滤**。
# 每日热点的英文源（HN / Reddit / arXiv）里偶尔混进色情、暴力、敏感政治类标题，
# 直接塞进提示词会被服务商内容审核整条拒掉（HTTP 400 badreq），
# 结果就是整篇教程生成失败。这里先在入口把它们剔掉，保证生成链路可用。
UNSAFE_WORDS = [
    "sex", "porn", "nsfw", "nude", "naked", "erotic", "escort", "cult",
    "suicide", "kill", "murder", "gore", "terror", "drug", "cocaine",
    "色情", "裸", "黄色网站", "自杀", "赌博", "毒品", "暴恐", "血腥",
    "邪教", "政变", "选举舞弊",
]


def is_safe(text):
    """粗筛：命中敏感词就不喂给模型（宁可少一条素材，也不要整批被拒）。"""
    t = (text or "").lower()
    return not any(w in t for w in UNSAFE_WORDS)


# ---------- 1. 读热点 ----------
def load_news():
    """读取 data/news/*.json（跳过 _ 开头的模板），返回扁平条目列表。"""
    items = []
    if not NEWS_DIR.exists():
        return items
    for p in sorted(NEWS_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            raw = d.get("items") or []
        elif isinstance(d, list):
            raw = d
        else:
            continue
        for it in raw:
            if isinstance(it, dict) and it.get("title"):
                items.append(it)
    return items


def haystack(it):
    """把一条热点压成一坨可检索文本（标题 / 摘要 / 标签 / 实体）。"""
    parts = [it.get("title") or "", it.get("summary") or ""]
    tags = it.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags)
    ent = it.get("entities") or {}
    if isinstance(ent, dict):
        for v in ent.values():
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
    return " ".join(parts).lower()


def news_date(it):
    for k in ("date", "publishedAt"):
        v = str(it.get(k) or "")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v.strip())
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def pick_by_topic(topic, news):
    """返回该话题命中的热点（按日期倒序，最多 MAX_NEWS_PER_TOPIC 条）。"""
    cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    hits = []
    for it in news:
        h = haystack(it)
        if not is_safe(h):
            continue
        if not any(sig.lower() in h for sig in topic["signals"]):
            continue
        dt = news_date(it)
        if dt and dt < cutoff:
            continue
        hits.append((dt or "0000-00-00", it))
    hits.sort(key=lambda x: x[0], reverse=True)
    # 同标题去重
    seen, out = set(), []
    for _, it in hits:
        t = (it.get("title") or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(it)
        if len(out) >= MAX_NEWS_PER_TOPIC:
            break
    return out


# ---------- 2. 提示词 ----------
PROMPT = """你在给「完全不懂技术、刚接触 AI 的中国新手」写一篇**照着做就能出结果**的实操教程。

话题：{title}
现在主流可行的工具方向：{tools}

下面是最近的真实热点（只能依据它们来写「为什么现在值得学」，**不许编造热点里没有的产品功能、价格、日期**）：
{listing}

请输出 JSON（不要任何解释、不要 markdown 代码块）：
{{
  "oneline": "25 字以内一句话说清这篇教什么，加粗核心词",
  "why": "80-140 字。结合上面的热点说清：为什么最近这件事值得学、学会了能解决什么实际问题",
  "steps": [{{"t": "步骤小标题（10 字内）", "d": "具体怎么做，**至少 40 个汉字**，写到「点哪里、填什么、写什么提示词」的程度，空话一律不算数"}}],
  "pitfalls": ["新手最容易踩的坑 3 条，各 20-40 字，含国内访问/收费/隐私等现实问题"],
  "action": "一句话：今天花 15 分钟就能做完的第一个动作",
  "tries": ["3 条可以照着抄的中文提示词示例，每条 20-40 字，用「」包住"]
}}

铁律：
1. steps 必须**正好 5 步**，而且是真的有先后顺序的操作流程，不能写成并列的功能介绍。
2. 每一条 step 的 d 都**不得少于 40 个汉字**，否则直接判定不合格。
3. 绝对不要出现代码、命令行、JSON、变量名、英文术语堆砌；用中文大白话。
4. 不要出现任何网址、也不要说「点击这里」之类的固定链接（站内不给外链）。
5. 关键按钮名、关键数字、关键提示词用 **双星号** 加粗。
6. 面向国内用户：工具优先写国内能直接用的；如果事件涉及国内用不了的产品，在 pitfalls 里说清并能给出替代思路。
只输出那个 JSON 对象。"""


def listing_for(items):
    lines = []
    for i, it in enumerate(items, 1):
        t = (it.get("title") or "").strip()[:60]
        s = (it.get("summary") or "").strip()[:110]
        if not is_safe(t + s):   # 双保险：进提示词前再筛一次
            continue
        src = (it.get("source") or "").strip()[:20]
        d = news_date(it)
        lines.append(f"{i}. [{d}] {t}（来源：{src}）\n   摘要：{s}")
    return "\n".join(lines) if lines else "（暂无）"


def valid(data):
    """质量门槛：不合格就重试，宁可写骨架也不写空话。"""
    if not isinstance(data, dict):
        return False
    steps = data.get("steps")
    if not isinstance(steps, list) or len(steps) != 5:
        return False
    for s in steps:
        if not isinstance(s, dict):
            return False
        t = str(s.get("t") or "").strip()
        d = str(s.get("d") or "").strip()
        if len(t) < 2 or len(d) < 18:
            return False
    if len(str(data.get("why") or "")) < 45:
        return False
    if not isinstance(data.get("pitfalls"), list) or len(data["pitfalls"]) < 2:
        return False
    return True


def choose_provider(ai):
    """用户要求优先用 DeepSeek。配了 DeepSeek 就用它；没配就退回网关自动链
    （当前只有智谱可用）。绝不强制调用未配置的供应商，避免直接报错失去兜底。"""
    if ai and callable(getattr(ai, "usable", None)) and ai.usable("deepseek"):
        return "deepseek"
    return None


# ---------- 3. 渲染 ----------
def bold_key(text):
    """把关键数字加粗（已是 ** 的片段跳过）。"""
    if not text:
        return text
    out = []
    for seg in re.split(r"(\*\*[^*]+\*\*)", str(text)):
        if seg.startswith("**"):
            out.append(seg)
            continue
        seg = re.sub(r"(\d+(?:\.\d+)?\s*(?:倍|%|％|分钟|小时|天|步|个|条|款|元|美元|秒))",
                     r"**\1**", seg)
        out.append(seg)
    return "".join(out)


def news_block(items):
    """「这周大家在聊什么」——站内链接列表，保证不出现外链。"""
    L = []
    for it in items:
        t = (it.get("title") or "").strip()
        link = (it.get("link") or "").strip()
        src = (it.get("source") or "").strip()
        d = news_date(it)
        meta = " · ".join([x for x in (src, d) if x])
        if link and link.endswith(".html"):
            L.append(f"- [{t}]({link})" + (f" —— {meta}" if meta else ""))
        else:
            L.append(f"- {t}" + (f" —— {meta}" if meta else ""))
    return "\n".join(L) if L else "- 暂无"


def skeleton_data(topic, items):
    """没有 AI 时的白话骨架：步骤是通用但真的能照做的流程。"""
    tools = topic["tools"]
    return {
        "oneline": f"**5 步**把 {topic['title']} 跑通，新手也能出第一个结果",
        "why": (
            f"最近这段时间，关于「{topic['title']}」的消息明显变多了（本页底部列了 **{len(items)}** 条站内热点）。"
            f"这类事的特点是：**门槛已经被拉低了**——你不需要懂原理，只要会打字、会点按钮，"
            f"就能在半小时内做出一个能拿给别人看的结果。先跑通一遍，比看十篇分析更有用。"
        ),
        "steps": [
            {"t": "先挑一个工具", "d": f"不要同时试很多个。从 {tools} 里**只挑一个**，注册好账号、登录进主界面。"},
            {"t": "想清楚要什么", "d": "用一句大白话写下你要的结果，例如「给一条 15 秒的产品介绍」「把我这段文字变成图」。写在纸上或备忘录里。"},
            {"t": "写第一条指令", "d": "把刚才那句话改写成三句话：**要做什么**、**给谁看**、**什么风格**。分点写清楚，别用长句。"},
            {"t": "生成第一版", "d": "粘进去、点生成，**不要挑剔第一版**。第一版的作用是让你知道这个工具的脾气，不是拿来做成品。"},
            {"t": "只改一个地方", "d": "在指令里**只改一处**再生成一次（比如换风格、换长度）。对比两版差异，重复 2-3 次，基本就能出能用的结果了。"},
        ],
        "pitfalls": [
            "**一次只改一个地方**：同时改三个条件，你根本不知道是哪句起了作用。",
            "**免费额度有限**：先挑有免费试用的工具跑通流程，再决定要不要付费。",
            "**别把隐私内容丢进去**：身份证、客户名单、公司内部文档，先脱敏再给 AI。",
        ],
        "action": f"今天花 15 分钟：挑一个工具注册好，把「{topic['title']}」跑出**第一个能看的结果**（哪怕很粗糙）。",
        "tries": [
            f"「帮我用{topic['title']}，输出一个给完全外行看的版本」",
            "「先说结论，再用 3 个要点解释，每点不超过 20 字」",
            "「给我 3 个不同风格的选择，并说明各自适合什么场合」",
        ],
    }


def render(topic, items, d, ai_ok):
    L = [f'<img class="cl-article-cover" src="{topic["cover"]}" alt="" loading="lazy">', ""]
    L += ['<div class="cl-meta">']
    L += ['  <span class="cl-meta-item">🔥 热点实操</span>']
    L += [f'  <span class="cl-meta-item">🗓 更新于 {datetime.now().strftime("%Y-%m-%d")}</span>']
    L += [f'  <span class="cl-meta-item">📌 基于 {len(items)} 条近期热点</span>']
    L += ['</div>', ""]
    L += [f"# {topic['title']}：5 步操作指南", ""]

    if d.get("oneline"):
        L += ['<Callout type="info" title="一句话看懂">', bold_key(d["oneline"]), "</Callout>", ""]
    if d.get("why"):
        L += ["## 为什么现在值得学", "", bold_key(d["why"]), ""]

    L += ["## 这周大家在聊什么", "", news_block(items), ""]

    steps = [s for s in (d.get("steps") or []) if isinstance(s, dict) and s.get("t")]
    if steps:
        L += ["## 五步实操：跟着做一遍", "", "<Steps>"]
        for s in steps:
            t = str(s.get("t", "")).strip().replace('"', "&quot;")
            detail = str(s.get("d", "")).strip()
            L.append(f'<Step title="{t}">{bold_key(detail)}</Step>' if detail else f'<Step title="{t}"></Step>')
        L += ["</Steps>", ""]

    tries = [x for x in (d.get("tries") or []) if str(x).strip()]
    if tries:
        L += ['<Callout type="tip" title="可以直接抄的中文提示词">', ""]
        for x in tries:
            L.append(f"- {str(x).strip()}")
        L += ["</Callout>", ""]

    pits = [x for x in (d.get("pitfalls") or []) if str(x).strip()]
    if pits:
        L += ['<Callout type="warn" title="新手最容易踩的坑">', ""]
        for x in pits:
            x = str(x).strip()
            if "**" not in x:
                x = f"**{x}**"
            L.append(f"- {x}")
        L += ["</Callout>", ""]

    if d.get("action"):
        L += ["## 今天就能做的一件事", "", bold_key(d["action"]), ""]

    L += ["---", "",
          "> 本页由站点自动整理近期热点生成，**每跑一次更新一次**；"
          "内容只依据上方列出的站内热点，不引用外部链接。", ""]
    if not ai_ok:
        L += ["> ⚠️ 本次是**无 AI 的骨架版**（模型暂时不可用），下次运行会自动升级成完整教程。", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="已生成过的也重跑")
    ap.add_argument("--max-topics", type=int, default=len(TOPICS))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    news = load_news()
    print(f"热点素材：{len(news)} 条")
    if not news:
        print("  没有可用的热点数据，跳过")
        return

    ai = None
    if not args.dry_run:
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            ai = AI(cfg)
        except Exception as e:
            print(f"  AI 初始化失败（将生成骨架版）：{e}")
            ai = None
    ai_on = bool(ai and ai.enabled)
    prov = choose_provider(ai)
    prov_name = prov or ("网关自动链（当前=%s）" % (ai.provider_name if ai else "无"))
    print(f"AI 状态：{'已启用' if ai_on else '未启用（生成骨架版）'}")
    print(f"优先供应商：{prov_name}\n")

    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    done, skipped = 0, 0

    for topic in TOPICS[: args.max_topics]:
        items = pick_by_topic(topic, news)
        if len(items) < MIN_ITEMS:
            print(f"  · {topic['title']}：只命中 {len(items)} 条（<{MIN_ITEMS}），跳过")
            skipped += 1
            continue

        out_path = SCENES_DIR / f"hot-{topic['slug']}.md"
        if out_path.exists() and not args.force and not args.dry_run:
            fm0, _ = split_md(out_path)
            if fm0.get("hot"):
                print(f"  · {topic['title']}：已是最新（{len(items)} 条热点）")
                continue

        print(f"  · {topic['title']}：命中 {len(items)} 条热点 → {out_path.name}")
        if args.dry_run:
            done += 1
            continue

        data, ok = None, False
        if ai_on:
            for attempt in range(1, 4):
                try:
                    cand = ai.json(PROMPT.format(title=topic["title"], tools=topic["tools"],
                                                 listing=listing_for(items)), provider=prov)
                except Exception:
                    cand = None
                if valid(cand):
                    data, ok = cand, True
                    break
                time.sleep(float(2))
            if not ok:
                print("      ！AI 连续 3 次返回不达标（或触发风控），改用骨架版")

        if not ok:
            data = skeleton_data(topic, items)

        fm_old = {}
        if out_path.exists():
            try:
                fm_old, _ = split_md(out_path)
            except Exception:
                fm_old = {}
        fm = {
            "title": f"{topic['title']}：5 步操作指南（热点实操）",
            "category": "热点实操",
            "emoji": topic["emoji"],
            "desc": re.sub(r"\*\*", "", str(data.get("oneline") or ""))[:120],
            "cover": topic["cover"],
            "auto": True,
            "updated": datetime.now().strftime("%Y-%m-%d"),
        }
        if ok:
            fm["hot"] = True          # 达标标记：下次运行跳过；不达标则不写，以便自动重试
        elif fm_old.get("hot"):
            fm["hot"] = True          # 曾经达标过，这次只是模型抖动，保留标记避免无意义重跑

        try:
            out_path.write_text(dump_md(fm, render(topic, items, data, ok)),
                                encoding="utf-8", newline="\n")
            done += 1
            print(f"      ✓ {'AI 版' if ok else '骨架版'}")
        except Exception as e:
            print(f"      ！写入失败，跳过：{e}")
            skipped += 1
        time.sleep(float(1))

    print(f"\n  完成：更新 {done} 篇，跳过 {skipped} 个话题")


if __name__ == "__main__":
    main()
