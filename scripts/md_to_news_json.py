# -*- coding: utf-8 -*-
"""
把「手工精选」格式的 markdown 转成网站用的 data/news/YYYY-MM-DD.json

用法：
    python scripts/md_to_news_json.py data/news/2026-09-10-手工精选.md

规则：
- 同一天已存在的文件会被**合并**，不会覆盖掉已有的其它条目
- 按「原文链接」匹配：链接相同就更新那条，链接不同就新增
- 文件名里的日期优先取正文 `## YYYY-MM-DD` 那行
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_NEWS = ROOT / "data" / "news"

# 只有这些才算「新字段」，其余 "- xxx" 一律当作上一个字段的续行
KNOWN = [
    "来源", "发布时间", "原文链接", "图片链接", "一句话摘要",
    "详细摘要", "关键要点", "重要原文摘录", "涉及公司/模型", "标签", "学习建议",
]

SPLIT = re.compile(r"[、,，/|]+")


def parse_md(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"^##\s+(\d{4}-\d{2}-\d{2})", text, re.M)
    if m:
        date = m.group(1)
    else:
        digits = re.sub(r"\D", "", path.stem)[:8]
        date = "%s-%s-%s" % (digits[:4], digits[4:6], digits[6:8])

    items = []
    for block in re.split(r"^###\s+", text, flags=re.M)[1:]:
        lines = block.split("\n")
        title = re.sub(r"^\d+[.、]\s*", "", lines[0].strip())
        data, cur = {}, None
        for line in lines[1:]:
            line = line.rstrip()
            if not line.strip():
                continue
            m2 = re.match(r"^-\s*([^：:]+)[：:]\s*(.*)$", line)
            if m2 and m2.group(1).strip() in KNOWN:
                cur = m2.group(1).strip()
                val = m2.group(2).strip()
                data[cur] = val if cur not in data else data[cur] + "\n" + val
                continue
            m3 = re.match(r"^-\s+(.*)$", line)
            if m3 and cur:
                data[cur] = (data.get(cur, "") + "\n" + m3.group(1).strip()).strip()
        items.append((title, data))
    return date, items


def to_item(date, idx, title, d):
    points = [x.strip() for x in (d.get("关键要点") or "").split("\n") if x.strip()]
    quotes = []
    for q in [x.strip() for x in (d.get("重要原文摘录") or "").split("\n") if x.strip()]:
        quotes.append({"text": q.strip('"').strip("“").strip("”").strip(), "note": ""})

    advice = {"learn": "", "do": ""}
    for line in (d.get("学习建议") or "").split("\n"):
        line = line.strip()
        if line.startswith("今天学什么") or line.startswith("- 今天学什么"):
            advice["learn"] = re.sub(r"^[- ]*今天学什么[：:]?\s*", "", line)
        elif line.startswith("今天做什么") or line.startswith("- 今天做什么"):
            advice["do"] = re.sub(r"^[- ]*今天做什么[：:]?\s*", "", line)
        elif line and not advice["learn"]:
            advice["learn"] = line
        elif line:
            advice["do"] = (advice["do"] + " " + line).strip()

    pub = (d.get("发布时间") or date).strip()
    if len(pub) == 10:
        pub = pub + "T09:00:00+08:00"

    ents = [x.strip() for x in SPLIT.split(d.get("涉及公司/模型") or "") if x.strip()]
    return {
        "id": "%s-m%02d" % (date, idx),
        "title": title,
        "source": (d.get("来源") or "").strip(),
        "publishedAt": pub,
        "summary": (d.get("一句话摘要") or "").strip(),
        "detail": (d.get("详细摘要") or "").strip(),
        "points": points,
        "quotes": quotes[:3],
        "image": (d.get("图片链接") or "/covers/news/default.svg").strip(),
        "url": (d.get("原文链接") or "").strip(),
        "entities": {"companies": ents[:8], "models": [], "tools": []},
        "tags": [x.strip() for x in SPLIT.split(d.get("标签") or "") if x.strip()][:3],
        "advice": advice,
        "link": "",
        "source_file": "manual",
    }


def main():
    ap = argparse.ArgumentParser(description="手工热点 markdown → 网站 JSON")
    ap.add_argument("file", help="markdown 文件路径")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print("找不到文件：", path)
        return 1

    date, parsed = parse_md(path)
    new_items = [to_item(date, i, t, d) for i, (t, d) in enumerate(parsed, 1)]

    DATA_NEWS.mkdir(parents=True, exist_ok=True)
    out = DATA_NEWS / ("%s.json" % date)
    store = {"date": date, "items": []}
    if out.exists():
        try:
            store = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing = store.get("items", [])
    by_url = {it.get("url"): it for it in existing if it.get("url")}
    by_title = {it.get("title"): it for it in existing}

    added = updated = 0
    for ni in new_items:
        old = by_url.get(ni["url"]) if ni["url"] else None
        if not old:
            old = by_title.get(ni["title"])
        if old:
            # 保留原有 id：md 文件名就是 id，改了会和 md 底账对不上
            keep_id = old.get("id")
            old.update(ni)
            old["id"] = keep_id
            old.pop("source_file", None)
            updated += 1
        else:
            existing.append(ni)
            added += 1

    existing.sort(key=lambda x: str(x.get("publishedAt", "")), reverse=True)
    store["items"] = existing
    store["date"] = date
    out.write_text(json.dumps(store, ensure_ascii=False, indent=2),
                   encoding="utf-8", newline="\n")

    print("%s：新增 %d 条，更新 %d 条，该文件现有 %d 条"
          % (out.relative_to(ROOT), added, updated, len(existing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
