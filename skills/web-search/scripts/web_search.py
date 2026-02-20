#!/usr/bin/env python3
"""
网络搜索工具 — 三引擎自动切换，完全免费
基于 GitHub 大神方案：Google HTML 爬虫 + DuckDuckGo + Brave API

用法:
  python3 web_search.py "搜索关键词"
  python3 web_search.py "关键词" --engine google     # Google（推荐，质量最好）
  python3 web_search.py "关键词" --engine ddg         # DuckDuckGo
  python3 web_search.py "关键词" --engine brave       # Brave（需 API Key）
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.parse
import re
import random


# ========== SSL 上下文（解决 macOS 自签名证书问题）==========
def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ========== User-Agent 池（防反爬）==========
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def _ua():
    return random.choice(USER_AGENTS)


# ========== Google 搜索（免费爬虫，灵感来自 github.com/pskill9/web-search）==========
def google_search(query, num_results=5):
    """Google HTML 爬虫搜索 — 免费，质量最高"""
    params = urllib.parse.urlencode({
        "q": query,
        "num": num_results + 2,  # 多请求几个防止过滤
        "hl": "zh-CN",
        "gl": "cn"
    })
    url = f"https://www.google.com/search?{params}"

    req = urllib.request.Request(url, headers={
        "User-Agent": _ua(),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
    })

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"⚠️ Google 搜索失败: {e}", file=sys.stderr)
        return []

    results = []

    # 方法1: 提取 <a href="/url?q=..." 格式的链接
    pattern = r'<a[^>]+href="/url\?q=([^&"]+)[^"]*"[^>]*>(.*?)</a>'
    matches = re.findall(pattern, html, re.DOTALL)

    seen_urls = set()
    for raw_url, raw_title in matches:
        url = urllib.parse.unquote(raw_url)

        # 过滤 Google 自身链接
        if any(skip in url for skip in ['google.com', 'youtube.com/results', 'accounts.google',
                                         'support.google', 'maps.google', 'translate.google']):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = re.sub(r'<[^>]+>', '', raw_title).strip()
        if not title:
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": ""
        })

        if len(results) >= num_results:
            break

    # 提取摘要（snippets）
    snippet_patterns = [
        r'<span class="(?:st|aCOpRe)"[^>]*>(.*?)</span>',
        r'<div class="(?:BNeawe s3v9rd|IsZvec)"[^>]*>(.*?)</div>',
        r'data-sncf="[^"]*"[^>]*>(.*?)</(?:span|div)>',
    ]
    all_snippets = []
    for sp in snippet_patterns:
        found = re.findall(sp, html, re.DOTALL)
        all_snippets.extend(found)

    for i, r in enumerate(results):
        if i < len(all_snippets):
            r["snippet"] = re.sub(r'<[^>]+>', '', all_snippets[i]).strip()[:200]

    return results


# ========== DuckDuckGo 搜索（免费备选）==========
def ddg_search(query, num_results=5):
    """DuckDuckGo HTML 搜索（完全免费，无需 API Key）"""
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query, "kl": "cn-zh"}).encode()

    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": _ua(),
        "Content-Type": "application/x-www-form-urlencoded"
    })

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"⚠️ DuckDuckGo 搜索失败: {e}", file=sys.stderr)
        return []

    results = []
    pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>'
    matches = re.findall(pattern, html)
    snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

    for i, (href, title) in enumerate(matches[:num_results]):
        actual_url = href
        uddg_match = re.search(r'uddg=([^&]+)', href)
        if uddg_match:
            actual_url = urllib.parse.unquote(uddg_match.group(1))
        clean_title = re.sub(r'<[^>]+>', '', title).strip()
        snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
        results.append({"title": clean_title, "url": actual_url, "snippet": snippet})

    return results


# ========== Brave Search API（需要 API Key，但质量好）==========
def brave_search(query, api_key, num_results=5):
    """Brave Search API（每月免费 $5 额度 ≈ 1000次搜索）"""
    params = urllib.parse.urlencode({
        "q": query, "count": num_results,
        "search_lang": "zh-hans", "text_decorations": "false"
    })
    url = f"https://api.search.brave.com/res/v1/web/search?{params}"

    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    })

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            raw = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Brave 搜索失败: {e}", file=sys.stderr)
        return []

    results = []
    for item in data.get("web", {}).get("results", [])[:num_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", "")
        })
    return results

# ========== 网页正文抓取（本地版 Perplexity 的核心）==========
def fetch_page(url, max_chars=6000):
    """抓取网页并提取正文（HTML → 纯文本）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": _ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "DNT": "1",
    })

    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return {"url": url, "error": f"非文本内容: {content_type}"}

            # 处理编码
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].strip().split(";")[0]

            raw = resp.read()
            # 尝试 gzip 解压
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)

            html = raw.decode(charset, errors="ignore")
    except Exception as e:
        return {"url": url, "error": str(e)}

    # 提取标题
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""

    # 移除脚本、样式、导航等非正文内容
    for tag in ['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe', 'svg']:
        html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # 移除 HTML 注释
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    # 尝试提取正文容器（按优先级尝试多种选择器）
    article = ""
    selectors = [
        r'<article[^>]*>(.*?)</article>',
        r'<main[^>]*>(.*?)</main>',
        r'<div[^>]*class="[^"]*(?:article|artibody|art_content|post_body|news_content|content_text|main-content|entry-content|post-content|article-body|article-content|news-body|detail-body|text-content|story-body|article-text|rich_media_content)[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id="[^"]*(?:article|artibody|content|main|post|entry|story)[^"]*"[^>]*>(.*?)</div>',
        r'<section[^>]*class="[^"]*(?:content|article|post|entry)[^"]*"[^>]*>(.*?)</section>',
    ]
    for selector in selectors:
        match = re.search(selector, html, re.DOTALL | re.IGNORECASE)
        if match and len(match.group(1)) > 200:  # 至少 200 字符才算有效
            article = match.group(1)
            break

    # 如果没找到文章容器，用整个 body 内的 <p> 标签拼接
    if not article:
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            article = '\n\n'.join(paragraphs)
        else:
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
            article = body_match.group(1) if body_match else html

    # 转为纯文本
    # 段落和换行
    text = re.sub(r'<br\s*/?\s*>', '\n', article)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'</div>', '\n', text)
    text = re.sub(r'</(?:h[1-6]|li|tr)>', '\n', text)
    # 移除所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 解码 HTML 实体
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<')
    text = text.replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    # 清理多余空白
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    # 截断到合理长度
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... 全文已截断，共 {len(text)} 字符 ...]"

    return {
        "url": url,
        "title": title,
        "content": text,
        "length": len(text)
    }


def deep_search(query, num_results=5, fetch_top=3, engine="auto"):
    """深度搜索：搜索 + 自动抓取前 N 篇网页全文"""
    brave_key = os.environ.get("BRAVE_API_KEY", "")

    # 1. 先搜索
    if engine == "auto":
        engine = "brave" if brave_key else "google"

    results = []
    if engine == "brave" and brave_key:
        results = brave_search(query, brave_key, num_results)
    if engine == "google" or not results:
        results = google_search(query, num_results)
    if not results:
        results = ddg_search(query, num_results)

    if not results:
        return {"query": query, "results": [], "pages": []}

    # 2. 抓取前 N 个结果的网页全文
    pages = []
    for r in results[:fetch_top]:
        url = r.get("url", "")
        if not url or not url.startswith("http"):
            continue

        print(f"📖 正在读取: {r.get('title', url)[:50]}...", file=sys.stderr)
        page = fetch_page(url)
        if "error" not in page:
            pages.append(page)

    return {"query": query, "results": results, "pages": pages}


# ========== 主程序 ==========
def main():
    parser = argparse.ArgumentParser(description="网络搜索（Google/DuckDuckGo/Brave 三引擎 + 网页抓取）")
    parser.add_argument("query", nargs="?", help="搜索关键词")
    parser.add_argument("--num", "-n", type=int, default=5, help="结果数量 (默认: 5)")
    parser.add_argument("--engine", "-e", choices=["auto", "google", "ddg", "brave"], default="auto",
                        help="搜索引擎 (默认: auto → Google → DDG 自动降级)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # 网页抓取模式
    parser.add_argument("--fetch", metavar="URL", help="抓取指定 URL 的网页正文")
    parser.add_argument("--max-chars", type=int, default=6000, help="抓取最大字符数 (默认: 6000)")

    # 深度搜索模式（= 搜索 + 抓取，本地版 Perplexity）
    parser.add_argument("--deep", action="store_true",
                        help="深度搜索：搜索后自动抓取前 3 篇网页全文（本地版 Perplexity）")
    parser.add_argument("--fetch-top", type=int, default=3, help="深度搜索时抓取前 N 篇 (默认: 3)")

    args = parser.parse_args()
    brave_key = os.environ.get("BRAVE_API_KEY", "")

    # ===== 模式 1: 网页抓取 =====
    if args.fetch:
        result = fetch_page(args.fetch, args.max_chars)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if "error" in result:
                print(f"❌ 抓取失败: {result['error']}")
            else:
                print(f"📄 {result['title']}")
                print(f"🔗 {result['url']}")
                print(f"📏 {result['length']} 字符")
                print(f"{'='*60}")
                print(result['content'])
        return

    # ===== 模式 2: 深度搜索（本地版 Perplexity）=====
    if args.deep and args.query:
        print(f"🔬 深度搜索: {args.query}\n", file=sys.stderr)
        result = deep_search(args.query, args.num, args.fetch_top, args.engine)

        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"🔬 深度搜索: {args.query}")
            print(f"📊 找到 {len(result['results'])} 个结果，已读取 {len(result['pages'])} 篇全文\n")

            # 先显示搜索结果列表
            print("━━━ 搜索结果 ━━━")
            for i, r in enumerate(result['results'], 1):
                print(f"[{i}] {r['title']}")
                print(f"    🔗 {r['url']}")
                if r.get('snippet'):
                    print(f"    📝 {r['snippet'][:120]}")
                print()

            # 再显示抓取的全文
            for i, page in enumerate(result['pages'], 1):
                print(f"━━━ 全文 [{i}] {page.get('title', '未知标题')[:60]} ━━━")
                print(f"🔗 {page['url']}")
                print(f"📏 {page['length']} 字符\n")
                print(page['content'][:3000])
                if page['length'] > 3000:
                    print(f"\n[... 余下 {page['length'] - 3000} 字符已省略 ...]")
                print()
        return

    # ===== 模式 3: 普通搜索 =====
    if not args.query:
        parser.print_help()
        return

    # 自动选择引擎优先级: Brave(有Key) > Google > DuckDuckGo
    if args.engine == "auto":
        if brave_key:
            engine = "brave"
        else:
            engine = "google"
    else:
        engine = args.engine

    # 执行搜索（带自动降级）
    results = []
    engine_used = engine

    if engine == "brave":
        if not brave_key:
            print("⚠️ 未设置 BRAVE_API_KEY，切换到 Google", file=sys.stderr)
            engine = "google"
        else:
            results = brave_search(args.query, brave_key, args.num)

    if engine == "google":
        results = google_search(args.query, args.num)
        engine_used = "Google"
        if not results:
            print("⚠️ Google 无结果，降级到 DuckDuckGo", file=sys.stderr)
            results = ddg_search(args.query, args.num)
            engine_used = "DuckDuckGo"

    if engine == "ddg":
        results = ddg_search(args.query, args.num)
        engine_used = "DuckDuckGo"

    # 输出
    if args.json:
        print(json.dumps({"engine": engine_used, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"🔍 [{engine_used}] 搜索: {args.query}\n")
        if not results:
            print("未找到结果。")
            return
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['title']}")
            print(f"    🔗 {r['url']}")
            if r['snippet']:
                print(f"    📝 {r['snippet'][:150]}")
            print()


if __name__ == "__main__":
    main()

