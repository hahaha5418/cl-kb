#!/usr/bin/env python3
"""今日待办清单生成器 —— 把「资讯」变成「行动」。

每天根据最新热点，自动生成两份清单（内容一致、用途不同）：
  1. TODAY_TODO.md     仓库根目录，用户本地速览
  2. docs/today.md     站点「今日冲刺」页数据源（/today.html 时光引擎会解析它）

生成逻辑（零 AI 依赖，断网也能跑）：
  - 扫描近 N 天热点，用 build_hotspot_tutorials 的话题信号匹配出「今天最值得动手的方向」
  - 命中的实操教程拆成 3 个任务（先看指南 → 做第 1-2 步 → 做第 3-4 步并打卡）
  - 没命中任何教程时，回退到学习路径轮换任务（与 ai_enrich.tasks 同规则）
  - 附当天值得看的新热点 5 条

用法：python scripts/build_today_todo.py [--days 2]
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CST = timezone(timedelta(hours=8))

sys.path.insert(0, str(Path(__file__).parent))
import build_hotspot_tutorials as B  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TODAY_SITE = DOCS / "today.md"
TODAY_LOCAL = ROOT / "TODAY_TODO.md"
PATH_DIR = DOCS / "path"
NEWS_MD_DIR = DOCS / "news"

RECENT_MAX = 365


def today_str():
    return datetime.now(CST).strftime("%Y-%m-%d")


def load_recent_news(days=2):
    """近 N 天热点（复用 build_hotspot_tutorials 的加载器，不足时放宽窗口）。"""
    news = B.load_news()
    if len(news) >= 3:
        return news
    for wider in (5, 10, RECENT_MAX):
        cutoff = datetime.now(CST) - timedelta(days=wider)
        got = [it for it in news if news_date_ok(it, cutoff)]
        if len(got) >= 3:
            return got
    return news


def news_date_ok(it, cutoff):
    d = (it.get("date") or it.get("published") or "")
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d") >= cutoff
    except Exception:
        return True


RECENT_MAX = 365


def match_topic(news):
    """按命中数挑今天最值得动手的话题（素材≥1 即可，取前2）。"""
    scored = []
    for t in B.TOPICS:
        items = B.pick_by_topic(t, news)
        if items:
            scored.append((t, len(items)))
    scored.sort(key=lambda x: -x[1])
    return scored[:2]


def news_date(it):
    d = it.get("date") or it.get("published") or ""
    return str(d)[:10]


def pick_path_tasks(n=1):
    """学习路径里未完成的任务，按日期轮换取 n 个（与 ai_enrich.tasks 同规则）。"""
    items = []
    if not PATH_DIR.exists():
        return items
    for sd in sorted(PATH_DIR.iterdir()):
        if not sd.is_dir():
            continue
        for f in sorted(sd.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            m = re.match(r"^---\n(.*?)\n---", text, re.S)
            if not m:
                continue
            fm_text = m.group(1).replace("\r\n", "\n")
            fm = {}
            for line in fm_text.split("\n"):
                mm = re.match(r"^(\w+):\s*(.+?)\s*$", line)
                if mm:
                    fm[mm.group(1)] = mm.group(2).strip('"')
            if fm.get("done") == "true":
                continue
            items.append({
                "title": fm.get("title") or f.stem,
                "stage": sd.name.replace("stage-", "阶段"),
                "link": f"./path/{sd.name}/{f.name}",
                "order": int(fm.get("order") or 999) if str(fm.get("order", "")).isdigit() else 999,
            })
    items.sort(key=lambda x: (x["stage"], x["order"]))
    start = datetime.now(CST).day % max(1, len(items)) if items else 0
    return [items[(start + i) % len(items)] for i in range(min(n, len(items)))]


def pick_recent_news_md(n=5):
    """docs/news 下最新的 n 篇热点（带标题与日期）。"""
    if not NEWS_MD_DIR.exists():
        return []
    out = []
    for p in NEWS_MD_DIR.glob("*.md"):
        if p.name == "index.md":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        fm_text = m.group(1).replace("\r\n", "\n") if m else ""
        title, date = "", ""
        for line in fm_text.split("\n"):
            mm = re.match(r'^(title|date):\s*"?([^"]+?)"?\s*$', line)
            if mm:
                if mm.group(1) == "title":
                    title = mm.group(2)
                else:
                    date = mm.group(2)
        out.append({"title": title or p.stem, "link": f"./news/{p.name}", "date": date})
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return out[:n]


def build_lines(days):
    news = load_recent_news(days)
    topics = match_topic(news)
    today = today_str()
    tasks = []   # (title, link, sub)
    intro = ""

    if topics:
        t, cnt = topics[0]
        page = f"./scenes/hot-{t['slug']}.md"
        tut_title = f"{t['title']}（{t['emoji']} 实操教程）"
        tasks.append((f"看 5 步指南：{t['title']}（近{cnt}条热点都在说）", page, "热点驱动 · 3 分钟"))
        tasks.append((f"动手做：《{t['title']}》第 1-2 步，预计 15 分钟", page, "今日任务"))
        if len(topics) > 1:
            t2, c2 = topics[1]
            tasks.append((f"进阶选做：《{t2['title']}》第 1 步（{c2} 条热点相关）",
                          f"./scenes/hot-{t2['slug']}.md", "选做 · 10 分钟"))
        else:
            tasks.append((f"继续做：《{t['title']}》第 3 步并打卡", page, "今日任务 · 10 分钟"))
        intro = (f"今天的热点集中在「{t['title']}」方向，别只看新闻——照着站内 5 步指南动手做一轮，"
                 f"15 分钟就能有第一个成果。")
    else:
        for x in pick_path_tasks(3):
            tasks.append((x["title"], x["link"], f"{x['stage']} · 路径任务"))
        intro = "今天热点里没有直接能上手的教程方向，按学习路径稳步推进，一样算赢。"

    if len(tasks) < 3:
        for x in pick_path_tasks(3 - len(tasks)):
            tasks.append((x["title"], x["link"], f"{x['stage']} · 路径任务"))

    recent = pick_recent_news_md(5)

    lines = [
        "---",
        'title: "今日学习任务"',
        f'date: "{today}"',
        "---",
        "",
        "# 今日学习任务",
        "",
        f"> {today} · 热点驱动自动生成（build_today_todo.py）",
        "",
        '<div class="cl-hero-grad g-today"><span class="cl-hero-icon">🎯</span>'
        '<span class="cl-hero-text">今日待办 · 从资讯到行动</span></div>',
        "",
        intro,
        "",
        "## 今天做这几件事",
        "",
    ]
    for i, (title, link, sub) in enumerate(tasks, 1):
        lines.append(f"{i}. [{title}]({link})　<sub>{sub}</sub>")

    if recent:
        lines += ["", "## 今天值得看的新热点", ""]
        for it in recent:
            d = f"　<sub>{it['date']}</sub>" if it["date"] else ""
            lines.append(f"- [{it['title']}]({it['link']}){d}")

    lines += [
        "",
        "## 怎么打卡",
        "",
        "打开任务页，完成后到学习路径对应条目把 `done` 改成 `true` 即可；",
        "首页进度条会自动更新。断网也不用怕——本站支持 PWA 离线阅读。",
        "",
    ]
    return "\n".join(lines), topics


def main():
    days = 2
    if "--days" in sys.argv:
        try:
            days = int(sys.argv[sys.argv.index("--days") + 1])
        except Exception:
            pass
    content, topics = build_lines(days)
    TODAY_SITE.write_text(content, encoding="utf-8", newline="\n")
    # 本地速览版：加个抬头，内容一致
    local = ("<!-- 本文件由 scripts/build_today_todo.py 自动生成；"
             "站点版在 docs/today.md（/today.html） -->\n\n" + content)
    TODAY_LOCAL.write_text(local, encoding="utf-8", newline="\n")
    print(f"OK 已生成 TODAY_TODO.md + docs/today.md（{today_str()}）")
    for t, cnt in topics:
        print(f"   命中话题：{t['emoji']} {t['title']}（{cnt} 条热点）")
    if not topics:
        print("   无热点命中，使用学习路径回退方案")


if __name__ == "__main__":
    main()
