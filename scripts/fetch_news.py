#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 AI 热点抓取脚本
------------------------------------------------------------
从 feeds.json 里配置的 RSS 源抓最新文章，生成 Markdown 文件
放到 docs/news/ 下，之后由 VitePress 自动生成页面。

特点：
  · 只用 Python 标准库，CI 里不用 pip install 任何东西
  · 按链接去重，同一条新闻不会重复写入
  · 自动清理 60 天前由脚本生成的热点（手动写的不动）
  · 某个源挂了会自动跳过，不影响其他源

用法：
  python scripts/fetch_news.py            抓取并写入文件
  python scripts/fetch_news.py --dry-run  只看看会抓到什么，不写文件
  python scripts/fetch_news.py --check    只检测每个源是否可用
"""

import argparse
import html
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NEWS_DIR = ROOT / "docs" / "news"
FEEDS_FILE = ROOT / "scripts" / "feeds.json"
STATE_FILE = ROOT / "scripts" / "state.json"

CST = timezone(timedelta(hours=8))  # 北京时间
DUP_THRESHOLD = 0.6  # 标题相似度超过这个值就认为是同一条新闻
ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
UA = {"User-Agent": "Mozilla/5.0 (compatible; CL-AI-KB/1.0)"}

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def today():
    return datetime.now(CST).strftime("%Y-%m-%d")


def clean(text, limit=220):
    """去掉 HTML 标签、压缩空白、截断"""
    if not text:
        return ""
    t = html.unescape(TAG_RE.sub(" ", str(text)))
    t = WS_RE.sub(" ", t).strip()
    return t[:limit].rstrip() + "…" if len(t) > limit else t


def slugify(title, n=40):
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(title).lower())
    return (re.sub(r"-+", "-", s).strip("-")[:n].strip("-") or "news")


def fetch(url, timeout=20, retries=3):
    """带重试的请求，网络抖动或被限流时自动重试"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(2 * (i + 1))
    raise last


def norm_date(raw):
    """把各种奇怪的时间格式统一成 YYYY-MM-DD"""
    if raw:
        try:
            return parsedate_to_datetime(raw).astimezone(CST).strftime("%Y-%m-%d")
        except Exception:
            pass
        try:
            return datetime.fromisoformat(
                raw.replace("Z", "+00:00")
            ).astimezone(CST).strftime("%Y-%m-%d")
        except Exception:
            pass
    return today()


def _esc(chunk, key):
    """从 Anthropic 页面内嵌的 Sanity 数据里取字段（引号被转义过）"""
    m = re.search(r"\\\"%s\\\":\\\"(.*?)\\\"" % key, chunk, re.S)
    return m.group(1) if m else ""


def parse_anthropic(data):
    """
    Anthropic 官网没有 RSS，直接从 /news 页面内嵌的数据结构里提取文章。
    字段：slug -> 链接，title / summary / publishedOn
    """
    text = data.decode("utf-8", errors="ignore")
    out, seen = [], set()

    for chunk in text.split("\\\"_type\\\":\\\"post\\\"")[1:]:
        m_slug = re.search(
            r"\\\"slug\\\":\{\\\"_type\\\":\\\"slug\\\",\\\"current\\\":\\\"(.*?)\\\"", chunk
        )
        title = _esc(chunk, "title")
        if not m_slug or not title:
            continue
        link = "https://www.anthropic.com/news/" + m_slug.group(1)
        if link in seen:
            continue
        seen.add(link)
        out.append({
            "title": clean(html.unescape(title), 120),
            "link": link,
            "summary": clean(html.unescape(_esc(chunk, "summary")), 220),
            "date": (_esc(chunk, "publishedOn") or "")[:10] or today(),
        })
    return out


NONWORD = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
CJK = re.compile(r"[\u4e00-\u9fff]")
STOPWORDS = {
    "the", "a", "an", "of", "and", "for", "to", "in", "on", "with", "is", "are",
    "at", "by", "from", "that", "this", "it", "its", "as", "be", "we", "our", "you",
}


def norm_title(t):
    """保留空格：英文按词比较，中文按字比较"""
    t = NONWORD.sub(" ", str(t).lower())
    return re.sub(r"\s+", " ", t).strip()


def _tokens(n):
    words = {w for w in n.split() if len(w) > 1 and w not in STOPWORDS}
    return words | set(CJK.findall(n))


def title_sim(a, b):
    """标题相似度 0-1：英文按词、中文按字，再对中文补一层二元组"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    best = len(ta & tb) / len(ta | tb)

    ca, cb = "".join(CJK.findall(a)), "".join(CJK.findall(b))
    if len(ca) >= 6 and len(cb) >= 6:
        ga = {ca[i:i + 2] for i in range(len(ca) - 1)}
        gb = {cb[i:i + 2] for i in range(len(cb) - 1)}
        best = max(best, len(ga & gb) / max(1, len(ga | gb)))
    return best


def existing_titles():
    """已有热点文件的标题，用来跨天去重"""
    out = []
    if not NEWS_DIR.exists():
        return out
    for p in NEWS_DIR.glob("*.md"):
        if p.name == "index.md":
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:800]
        except Exception:
            continue
        m = re.search(r'^title:\s*"(.*?)"\s*$', head, re.M)
        if m:
            out.append(m.group(1))
    return out


BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def sanitize(data):
    """有些站点的 RSS 里混了非法字符，清掉再解析一次"""
    text = data.decode("utf-8", errors="ignore")
    return BAD_XML.sub("", text).encode("utf-8", errors="ignore")


def parse_feed(data):
    """同时兼容 RSS 2.0 和 Atom 两种格式"""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        root = ET.fromstring(sanitize(data))
    nodes = list(root.iter("item")) + list(root.iter(ATOM + "entry"))
    out = []

    for node in nodes:
        def pick(*names):
            for nm in names:
                el = node.find(nm)
                if el is not None and el.text and el.text.strip():
                    return el.text.strip()
            return ""

        title = clean(pick("title", ATOM + "title"), 120)
        summary = clean(pick("description", "summary", ATOM + "summary", CONTENT_NS), 220)

        link = ""
        for nm in ("link", ATOM + "link"):
            for el in node.findall(nm):
                if el.get("href"):
                    link = el.get("href")
                    break
                if el.text and el.text.strip():
                    link = el.text.strip()
                    break
            if link:
                break

        if title and link:
            out.append({
                "title": title,
                "link": link,
                "summary": summary,
                "date": norm_date(pick("pubDate", "published", ATOM + "published",
                                       "updated", ATOM + "updated")),
            })
    return out


def render(item):
    def q(s):
        return json.dumps(s, ensure_ascii=False)

    return "\n".join([
        "---",
        "title: " + q(item["title"]),
        "date: " + q(item["date"]),
        "source: " + q(item["source"]),
        "tag: " + q(item["tag"] or "AI"),
        "url: " + q(item["link"]),
        "auto: true",
        "---",
        "",
        "# " + item["title"],
        "",
        item["summary"] or "_（源站没有提供摘要）_",
        "",
        "> 来源：" + item["source"] + " · " + item["date"] + " · 由脚本自动抓取",
        "",
        "[阅读原文](" + item["link"] + ")",
        "",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    ap.add_argument("--check", action="store_true", help="只检测 RSS 源是否可用")
    ap.add_argument("--force", action="store_true", help="忽略去重，全部重新写入")
    args = ap.parse_args()

    cfg = json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
    feeds = cfg.get("feeds", [])
    max_per_feed = int(cfg.get("max_per_feed", 5))
    max_age_days = int(cfg.get("max_age_days", 5))
    keep_days = int(cfg.get("keep_days", 60))

    print(f"共配置 {len(feeds)} 个 RSS 源\n")

    if args.check:
        for f in feeds:
            try:
                n = len(parse_feed(fetch(f["url"])))
                print(f"  [可用] {f['name']}：{n} 条")
            except Exception as e:
                print(f"  [失败] {f['name']}：{type(e).__name__} {e}")
        return

    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {"seen": []}
    seen = set(state.get("seen", []))
    picked = []

    for f in feeds:
        name, url = f.get("name"), f.get("url")
        if not url:
            continue
        try:
            if f.get("type") == "anthropic":
                items = parse_anthropic(fetch(url))
            else:
                items = parse_feed(fetch(url))
        except Exception as e:
            print(f"  [跳过] {name}：{type(e).__name__} {e}")
            continue

        limit = int(f.get("max", max_per_feed))
        got = 0
        for it in items:
            if got >= limit:
                break
            if not args.force and it["link"] in seen:
                continue
            it["date"] = norm_date(it["date"])
            # 只要最近几天的新内容，避免把源站存档里的旧文章全倒进来
            try:
                age = (datetime.now(CST).date()
                       - datetime.strptime(it["date"], "%Y-%m-%d").date()).days
            except Exception:
                age = 0
            if age > max_age_days:
                continue
            it["source"] = name
            it["tag"] = f.get("tag", "")
            picked.append(it)
            seen.add(it["link"])
            got += 1
        print(f"  [完成] {name}：新增 {got} 条")

    print(f"\n本次共抓到 {len(picked)} 条，开始跨源去重…")

    # 同一条新闻常被多个源同时报道，按标题相似度去重，保留先抓到的（源顺序即优先级）
    known = [norm_title(t) for t in existing_titles()]
    kept, dups = [], []
    for it in picked:
        n = norm_title(it["title"])
        hit = next((k for k in known if title_sim(n, k) >= DUP_THRESHOLD), None)
        if hit:
            dups.append((it["source"], it["title"], hit[:40]))
            continue
        known.append(n)
        kept.append(it)

    if dups:
        print(f"  去重 {len(dups)} 条重复报道：")
        for src, t, _ in dups[:12]:
            print(f"    · [{src}] {t[:52]}")
    picked = kept
    print(f"  去重后剩 {len(picked)} 条")

    if args.dry_run:
        for it in picked:
            print(f"  · [{it['source']}] {it['title']}")
        return

    NEWS_DIR.mkdir(parents=True, exist_ok=True)
    for it in picked:
        target = NEWS_DIR / f"{it['date']}-{slugify(it['title'])}.md"
        n = 2
        while target.exists():
            target = NEWS_DIR / f"{it['date']}-{slugify(it['title'])}-{n}.md"
            n += 1
        target.write_text(render(it), encoding="utf-8", newline="\n")
        print(f"  写入 {target.name}")

    cutoff = (datetime.now(CST) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    removed = 0
    for p in NEWS_DIR.glob("*.md"):
        if p.name == "index.md":
            continue
        if "auto: true" not in p.read_text(encoding="utf-8")[:400]:
            continue
        if p.name[:10] < cutoff:
            p.unlink()
            removed += 1
    print(f"  清理 {keep_days} 天前的旧热点：{removed} 条")

    state["seen"] = sorted(seen)[-3000:]
    state["last_run"] = datetime.now(CST).isoformat(timespec="seconds")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n完成")


if __name__ == "__main__":
    main()
