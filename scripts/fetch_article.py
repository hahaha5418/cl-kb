#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_article.py —— 给 AI 装上的「网页浏览」手脚（纯标准库，零依赖）
=====================================================================
当自动抓到的热点内容不够详细时，让 AI 能：
  1) 自动抓取热点里的「原文链接」；
  2) 把 HTML 抽成干净的纯文本（去掉脚本/样式/导航/广告）；
  3) 把全文交给大模型做总结，而不是只盯着标题瞎编。

设计铁律：
  · 任何一步失败（超时 / 403 / 编码乱码 / 抽不出正文）→ 返回 None，绝不抛异常。
  · 默认超时 8 秒，单篇截断到 ~6000 字，避免把整站拖垮或烧 token。
  · 不依赖任何第三方库（requests/bs4 都不要），与全站零依赖约定保持一致。

用法：
  python scripts/fetch_article.py <url>            # 命令行测试：打印抽取到的纯文本
  python scripts/fetch_article.py <url> --max 4000 # 指定截断字数
在业务脚本里：
  from fetch_article import fetch_article
  text = fetch_article("https://...")
  if text:
      # 把 text 拼进给大模型的 prompt 作为真实素材
"""

import argparse
import gzip
import re
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

DEFAULT_TIMEOUT = 8
DEFAULT_MAX = 6000
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style|noscript|svg|head)[^>]*>[\s\S]*?</\1>", re.I)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def _decode(body: bytes, hint: str) -> str:
    """尽量用对编码解码（先看 HTTP 头，再看 <meta charset>，最后退回 utf-8 容错）。"""
    enc = None
    if hint:
        m = re.search(r"charset\s*=\s*([A-Za-z0-9\-]+)", hint, re.I)
        if m:
            enc = m.group(1).strip().lower()
    if not enc:
        try:
            head = body[:2000].decode("utf-8", "ignore")
            m = re.search(r"<meta[^>]+charset\s*=\s*[\"']?\s*([A-Za-z0-9\-]+)", head, re.I)
            if m:
                enc = m.group(1).strip().lower()
        except Exception:
            pass
    if enc in ("gb2312", "gbk"):
        enc = "gb18030"  # gb18030 向下兼容 gbk/gb2312
    if not enc:
        enc = "utf-8"
    return body.decode(enc, errors="ignore")


def _strip_html(html: str) -> str:
    """去掉脚本/样式，去标签，挤掉多余空白，保留正文段落感。"""
    html = _SCRIPT_RE.sub(" ", html)
    html = _TAG_RE.sub(" ", html)
    html = _CTRL_RE.sub(" ", html)
    # 把常见句子结尾标点后的标签位置补个换行，保留一点段落结构
    html = re.sub(r"([。！？!?；;])\s+", r"\1\n", html)
    html = _WS_RE.sub(" ", html)
    html = _NL_RE.sub("\n\n", html)
    return html.strip()


def fetch_article(url: str, *, timeout: int = DEFAULT_TIMEOUT,
                  max_chars: int = DEFAULT_MAX) -> str | None:
    """抓取并抽取一篇网页的正文纯文本。失败返回 None。"""
    if not url or not _URL_RE.match(url.strip()):
        return None
    url = url.strip()
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    try:
        resp = opener.open(req, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    try:
        raw = resp.read()
    except Exception:
        return None
    # 处理 gzip
    try:
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
    except Exception:
        return None
    ctype = resp.headers.get("Content-Type", "") or ""
    if "html" not in ctype.lower():
        # 非 HTML（图片/PDF 等）无法抽取正文
        return None
    text = _decode(raw, resp.headers.get("Content-Type", ""))
    text = _strip_html(text)
    text = re.sub(r"(?s)关注我们.*?(微信|公众号|扫码|点赞|在看|分享到)", " ", text)
    text = re.sub(r"\b(首页|登录|注册|下载APP|免责声明|版权所有)\b", " ", text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) < 120:
        return None  # 抽不出有效正文，宁可不要
    if max_chars and len(text) > max_chars:
        text = text[:max_chars]
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description="抓取网页并抽取纯文本（给 AI 用的「网页浏览」工具）")
    ap.add_argument("url")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = ap.parse_args(argv)
    t0 = time.time()
    text = fetch_article(args.url, timeout=args.timeout, max_chars=args.max)
    if not text:
        print(f"❌ 无法抽取正文（超时 / 非 HTML / 正文过短）：{args.url}")
        return 1
    print(f"✅ 抽取成功，{len(text)} 字，用时 {time.time() - t0:.2f}s\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
