# -*- coding: utf-8 -*-
"""
每日热点详情库 · 生成器
=====================

把 docs/news/*.md 里的热点，用 AI 整理成 12 字段的结构化详情，
按天写入 data/news/YYYY-MM-DD.json。

用法：
    python scripts/news_library.py gen            # 生成最近 2 天
    python scripts/news_library.py gen --days 7   # 生成最近 7 天
    python scripts/news_library.py gen --all      # 生成全部历史
    python scripts/news_library.py gen --force    # 已生成过的也重跑
    python scripts/news_library.py template       # 重写手动填写模板

没有配置 API Key 时脚本会优雅降级：不写文件、不影响其它流程。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_NEWS = ROOT / "docs" / "news"
DATA_NEWS = ROOT / "data" / "news"
CONFIG_FILE = ROOT / "scripts" / "ai_config.json"

sys.path.insert(0, str(ROOT / "scripts"))
from ai_enrich import AI  # noqa: E402


# ---------------- 基础工具 ----------------

def split_md(path):
    """拆出 frontmatter 字典和正文。"""
    raw = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
    fm, body = {}, raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$', line.strip())
                if not m:
                    continue
                k, v = m.group(1), m.group(2).strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                elif v in ("true", "false"):
                    v = (v == "true")
                fm[k] = v
            body = parts[2]
    return fm, body


def iso_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def read_day(day):
    p = DATA_NEWS / f"{day}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_day(day, obj):
    DATA_NEWS.mkdir(parents=True, exist_ok=True)
    p = DATA_NEWS / f"{day}.json"
    p.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )


# ---------------- AI 提示词 ----------------

SYSTEM = "你是资深 AI 资讯编辑，擅长把技术新闻讲清楚。只输出 JSON，不要任何解释。"

TAG_POOL = ("模型发布, AI编程, 视频生成, 音乐生成, 图像生成, Agent, "
            "芯片算力, 政策监管, 融资并购, 开源, 硬件终端, 行业动态")


def build_prompt(fm, body):
    plain = re.sub(r"<[^>]+>", " ", body or "")
    plain = re.sub(r"[ \t]+", " ", plain).strip()
    plain = plain[:700]

    return f"""请把下面这条 AI 行业热点，整理成结构化详情，给一个 AI 初学者看。

已知信息：
- 中文标题：{fm.get('title', '')}
- 英文原标题：{fm.get('title_en', '')}
- 来源：{fm.get('source', '')}
- 日期：{fm.get('date', '')}
- 现有摘要：{fm.get('summary_zh') or fm.get('summary', '')}
- 已有正文素材：{plain}

请只输出一个 JSON 对象，字段如下：
{{
  "summary": "一句话摘要，30-50 字，只讲清『谁做了什么』",
  "detail": "详细摘要，250-450 字。必须按这四层展开，每层都要有实质内容：①这条新闻具体说了什么事（2-3 句）；②背后的原因或行业背景（2-3 句）；③对行业、对普通用户分别意味着什么（2-3 句）；④目前有什么争议、局限或还不确定的地方（1-2 句）。",
  "points": ["关键要点", "...共 4-6 条"],
  "quotes": [{{"text": "原文中的关键句（能摘到英文原句就照抄，摘不到就用中文概括）", "note": "这句为什么重要，15-30 字"}}],
  "entities": {{"companies": ["公司名"], "models": ["模型名"], "tools": ["工具名"]}},
  "tags": ["从这些里选 1-3 个：{TAG_POOL}"],
  "advice": {{"learn": "今天应该弄懂的一个概念，20-40 字", "do": "今天可以做的一个具体动作，20-40 字，必须可操作"}}
}}

严格要求（违反即作废）：
1. 只输出 JSON，不要 markdown 代码块，不要任何解释文字。
2. detail 必须 250-450 字，且**不能是 summary 的同义扩写**，必须给出 summary 里没有的信息。
3. **禁止空洞套话**：不许出现「带来更多可能」「具有重要意义」「值得关注」「奠定基础」这类没有信息量的句子，每句话都要有具体内容。
4. points 必须 4-6 条，每条讲一个**不同维度**，从下面挑且不重复：
   - 事件本身：到底发生了什么
   - 技术或产品细节：它是怎么做到的
   - 背景与原因：为什么现在发生
   - 对行业或竞品的影响
   - 对普通用户、初学者的实际意义
   - 局限、争议或不确定性
   每条 20-45 字。**严禁两条表达同一个意思**，写不出来就少写几条，宁可 4 条也不要凑数重复。
5. **绝对不许编造**具体数字、日期、人名、型号。信息不足时用「据报道」「官方称」，或写常识性背景。
6. 全部用中文（quotes.text 可以是英文原句）。
"""


# ---------------- 要点去重 ----------------

def _sim(a, b):
    """字符级 Jaccard 相似度，用来识别换皮重复句。"""
    A, B = set(a), set(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def dedupe_points(points, thresh=0.58):
    """丢掉意思重复的要点，保留先出现的。"""
    out = []
    for p in points:
        p = p.strip()
        if len(p) < 8:
            continue
        if all(_sim(p, q) < thresh for q in out):
            out.append(p)
    return out


def needs_regen(it):
    """判断一条已存的详情是否还需要重做（字数不够 / 要点太少 / 要点有重复 / 要点过多）。"""
    d = str(it.get("detail") or "")
    p = [str(x) for x in (it.get("points") or [])]
    if len(d) < 200:
        return True
    if len(p) < 3 or len(p) > 6:
        return True
    if len(dedupe_points(p)) < len(p):
        return True  # 存在换皮重复要点
    return False


def expand_detail(ai, fm, draft):
    """详细摘要字数不够时，定向扩写一次（只补内容，不改已有事实）。"""
    n = len(draft)
    prompt = f"""下面是一段 AI 热点摘要草稿，只有 {n} 字，太短。请在草稿基础上扩写到 250-400 字。

标题：{fm.get('title', '')}
来源：{fm.get('source', '')}

草稿：
{draft}

扩写要求：
1. 保留草稿里已有的事实，不要删改。
2. 必须补上这三层，每层 2-3 句：
   ① 行业背景，或者这件事为什么现在才发生；
   ② 对行业、对普通用户/初学者分别意味着什么；
   ③ 目前有什么局限、争议或还不确定的地方。
3. 每句都要有具体信息，禁止「带来更多可能」「具有重要意义」「值得关注」这类空话。
4. 不要把草稿已有的句子换皮重写一遍。
5. 只输出扩写后的正文，不要 JSON、不要引号、不要小标题。
"""
    t = ai.call(prompt, system=SYSTEM, max_tokens=1200)
    if not t:
        return None
    return t.strip().strip('"').strip()


# ---------------- 核心：生成 ----------------

def gen(ai, days=None, all_days=False, force=False):
    if not ai.enabled:
        print("[详情库] 未配置 API Key，跳过生成（已有文件不受影响）")
        return 0

    files = sorted([f for f in DOCS_NEWS.glob("*.md") if f.name != "index.md"])
    by_day = {}
    for f in files:
        fm, body = split_md(f)
        day = (fm.get("date") or "")[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            continue
        by_day.setdefault(day, []).append((f, fm, body))

    all_days_list = sorted(by_day.keys(), reverse=True)
    if all_days:
        targets = all_days_list
    else:
        n = days or 2
        targets = all_days_list[:n]

    total = 0
    for day in targets:
        entries = by_day[day]
        store = read_day(day) or {"date": day, "items": []}
        known = {it.get("id"): it for it in store.get("items", [])}

        changed = False
        for f, fm, body in entries:
            _id = f.stem
            old = known.get(_id)
            # 已达标就跳过；任何一项不达标（或被 --force）都会重跑，实现自动补全
            if old and not force and not needs_regen(old):
                continue

            # 最多尝试 2 次：第一次不达标就重来，仍不达标才放弃（下次运行会自动重试）
            resp, detail, points = None, "", []
            for _attempt in range(2):
                r = ai.json(build_prompt(fm, body), system=SYSTEM, max_tokens=2000)
                if not r or not isinstance(r, dict):
                    continue
                d = str(r.get("detail") or "").strip()
                p = dedupe_points([str(x) for x in (r.get("points") or [])])[:6]
                if resp is None:
                    resp, detail, points = r, d, p
                if len(d) >= 200 and len(p) >= 3:
                    resp, detail, points = r, d, p
                    break

            if not resp:
                print(f"    [跳过] {fm.get('title', '')[:28]}")
                continue

            # 详细摘要偏短 → 定向扩写一次补足字数
            if 0 < len(detail) < 200:
                longer = expand_detail(ai, fm, detail)
                if longer and len(longer) > len(detail):
                    detail = longer

            if len(detail) < 200 or len(points) < 3:
                print(f"    [质量不足] {fm.get('title', '')[:28]}（{len(detail)}字 / {len(points)}要点）")
                continue

            ents = resp.get("entities") or {}
            adv = resp.get("advice") or {}
            tags = [str(t).strip() for t in (resp.get("tags") or []) if str(t).strip()][:3]

            item = {
                "id": _id,
                "title": fm.get("title") or f.stem,
                "source": fm.get("source") or "",
                "publishedAt": fm.get("updated") or (day + "T08:00:00+08:00"),
                "summary": str(resp.get("summary") or "").strip()[:80],
                "detail": detail,
                "points": points,
                "quotes": [
                    {"text": str(q.get("text", "")).strip(),
                     "note": str(q.get("note", "")).strip()}
                    for q in (resp.get("quotes") or [])
                    if isinstance(q, dict) and str(q.get("text", "")).strip()
                ][:3],
                "image": fm.get("cover") or "/covers/news/default.svg",
                "url": fm.get("url") or "",
                "entities": {
                    "companies": [str(x) for x in (ents.get("companies") or [])][:6],
                    "models": [str(x) for x in (ents.get("models") or [])][:6],
                    "tools": [str(x) for x in (ents.get("tools") or [])][:6],
                },
                "tags": tags or ["行业动态"],
                "advice": {
                    "learn": str(adv.get("learn") or "").strip(),
                    "do": str(adv.get("do") or "").strip(),
                },
                "link": "/news/" + f.name.replace(".md", ".html"),
                "generatedAt": iso_now(),
            }
            known[_id] = item
            changed = True
            total += 1
            print(f"    ✓ {item['title'][:30]}")

        if changed:
            store["items"] = sorted(
                known.values(),
                key=lambda x: str(x.get("publishedAt", "")),
                reverse=True,
            )
            store["updatedAt"] = iso_now()
            write_day(day, store)
            print(f"  → data/news/{day}.json（{len(store['items'])} 条）")

    print(f"  完成，共生成 {total} 条详情")
    return total


# ---------------- 手动模板 ----------------

TEMPLATE = {
    "date": "YYYY-MM-DD",
    "items": [
        {
            "id": "YYYY-MM-DD-英文短横线标识",
            "title": "标题（中文）",
            "source": "来源，如 OpenAI 官网 / Anthropic / 量子位 / TechCrunch",
            "publishedAt": "2026-09-10T08:30:00+08:00",
            "summary": "一句话摘要，30-50 字，讲清谁做了什么",
            "detail": "详细摘要，200-500 字：背景、做了什么、为什么重要、对普通人的影响",
            "points": ["关键要点 1（15-40 字）", "关键要点 2", "关键要点 3"],
            "quotes": [
                {"text": "原文关键句", "note": "这句为什么重要"}
            ],
            "image": "/covers/news/default.svg",
            "url": "https://原文链接",
            "entities": {
                "companies": ["公司名"],
                "models": ["模型名"],
                "tools": ["工具名"],
            },
            "tags": ["模型发布"],
            "advice": {
                "learn": "今天应该弄懂的一个概念",
                "do": "今天可以做的一个具体动作",
            },
            "link": "",
        }
    ],
}


def write_template():
    DATA_NEWS.mkdir(parents=True, exist_ok=True)
    p = DATA_NEWS / "_模板.json"
    p.write_text(
        json.dumps(TEMPLATE, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"模板已写入 {p.relative_to(ROOT)}")


def main():
    cfg = {}
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    ai = AI(cfg)

    ap = argparse.ArgumentParser(description="每日热点详情库生成器")
    ap.add_argument("mode", choices=["gen", "template"])
    ap.add_argument("--days", type=int, default=2, help="生成最近 N 天")
    ap.add_argument("--all", action="store_true", help="生成全部历史")
    ap.add_argument("--force", action="store_true", help="已生成的也重跑")
    args = ap.parse_args()

    if args.mode == "template":
        write_template()
        return
    gen(ai, days=args.days, all_days=args.all, force=args.force)


if __name__ == "__main__":
    main()
