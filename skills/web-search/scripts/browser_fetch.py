#!/usr/bin/env python3
"""
浏览器抓取工具 — 直接访问大众点评/小红书/知乎等平台
使用 Playwright + 用户 Chrome profile（复用已登录状态）

用法:
  python3 browser_fetch.py --search "外滩餐厅" --site dianping
  python3 browser_fetch.py "https://www.xiaohongshu.com/explore/xxx"
  python3 browser_fetch.py --login dianping

环境变量:
  PLAYWRIGHT_BROWSERS_PATH  — Playwright 浏览器路径
  CHROME_USER_DATA_DIR      — Chrome 用户数据目录（可选，默认自动检测）
"""

import argparse
import json
import os
import sys
import time
import re
import tempfile
import shutil
import urllib.parse

# ========== 路径配置 ==========
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_ROOT = os.environ.get("OPENCLAW_HOME", os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))

if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(OPENCLAW_ROOT, ".venv", "browsers")

# Cookie 持久化目录
COOKIE_DIR = os.path.join(OPENCLAW_ROOT, ".openclaw", "cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)

# Chrome Debug 端口
CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))

# Playwright 延迟导入
sync_playwright = None

def _ensure_playwright():
    global sync_playwright
    if sync_playwright is None:
        from playwright.sync_api import sync_playwright as sp
        sync_playwright = sp


def _check_cdp_port(port=None):
    """检查 Chrome Debug 端口是否可用"""
    port = port or CDP_PORT
    try:
        import urllib.request as ur
        req = ur.Request(f"http://127.0.0.1:{port}/json/version")
        with ur.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return data
    except Exception:
        return None


# ========== 平台配置 ==========

PLATFORMS = {
    "dianping": {
        "name": "大众点评",
        "domain": "dianping.com",
        "search_url": "https://www.dianping.com/search/keyword/{city_id}/0_{query}",
        "home_url": "https://www.dianping.com",
        "default_city": "1",  # 上海
        "cities": {"上海": "1", "北京": "2", "广州": "4", "深圳": "7", "杭州": "5", "南京": "9", "成都": "8", "武汉": "13", "西安": "17", "重庆": "30"},
    },
    "xiaohongshu": {
        "name": "小红书",
        "domain": "xiaohongshu.com",
        "search_url": "https://www.xiaohongshu.com/search_result?keyword={query}&source=web_search_result_note",
        "home_url": "https://www.xiaohongshu.com",
    },
    "xhs": {  # 小红书别名
        "name": "小红书",
        "domain": "xiaohongshu.com",
        "search_url": "https://www.xiaohongshu.com/search_result?keyword={query}&source=web_search_result_note",
        "home_url": "https://www.xiaohongshu.com",
    },
    "zhihu": {
        "name": "知乎",
        "domain": "zhihu.com",
        "search_url": "https://www.zhihu.com/search?type=content&q={query}",
        "home_url": "https://www.zhihu.com",
    },
    "weibo": {
        "name": "微博",
        "domain": "weibo.com",
        "search_url": "https://s.weibo.com/weibo?q={query}",
        "home_url": "https://weibo.com",
    },
    "bilibili": {
        "name": "B站",
        "domain": "bilibili.com",
        "search_url": "https://search.bilibili.com/all?keyword={query}",
        "home_url": "https://www.bilibili.com",
    },
}


# ========== Cookie 管理 ==========

def get_cookie_path(platform):
    return os.path.join(COOKIE_DIR, f"{platform}_cookies.json")

def save_cookies(context, platform):
    """保存浏览器 Cookie"""
    cookies = context.cookies()
    path = get_cookie_path(platform)
    with open(path, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookie 已保存到 {path} ({len(cookies)} 条)", file=sys.stderr)

def load_cookies(context, platform):
    """加载已保存的 Cookie"""
    path = get_cookie_path(platform)
    if os.path.exists(path):
        with open(path) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        print(f"🍪 已加载 {platform} Cookie ({len(cookies)} 条)", file=sys.stderr)
        return True
    return False


# ========== 浏览器启动 ==========

def create_browser_context(playwright, headless=True, mobile=False, use_cdp=False):
    """创建浏览器上下文，支持 CDP 连接和独立启动两种模式"""
    
    # 确保临时目录存在（macOS 权限问题）
    pw_tmp = os.path.join(OPENCLAW_ROOT, ".openclaw", "pw_tmp")
    os.makedirs(pw_tmp, exist_ok=True)
    os.environ["TMPDIR"] = pw_tmp
    
    # 模式1: CDP 连接已有 Chrome Debug 实例（推荐）
    if use_cdp:
        cdp_info = _check_cdp_port()
        if cdp_info:
            print(f"🔗 CDP 连接: Chrome {cdp_info.get('Browser', '')}", file=sys.stderr)
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
            # CDP 模式下使用已有的默认上下文
            if browser.contexts:
                ctx = browser.contexts[0]
                print(f"✅ 已连接（复用已登录会话）", file=sys.stderr)
                return browser, ctx
            else:
                ctx = browser.new_context(locale="zh-CN", timezone_id="Asia/Shanghai")
                return browser, ctx
        else:
            print(f"⚠️ CDP 端口 {CDP_PORT} 不可用，回退到独立 Chromium", file=sys.stderr)
    
    # 模式2: 独立 Playwright Chromium（headless）
    launch_args = [
        '--no-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
    ]
    
    browser = playwright.chromium.launch(
        headless=headless,
        args=launch_args,
    )
    
    context_opts = {
        "viewport": {"width": 1920, "height": 1080},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    
    if mobile:
        context_opts.update({
            "viewport": {"width": 390, "height": 844},
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
            "is_mobile": True,
        })
    
    ctx = browser.new_context(**context_opts)
    
    # 反检测脚本
    ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
        window.chrome = { runtime: {} };
    """)
    
    return browser, ctx


# ========== 登录流程 ==========

def login_platform(platform):
    """非 headless 浏览器登录，保存 Cookie"""
    config = PLATFORMS.get(platform)
    if not config:
        print(f"❌ 不支持的平台: {platform}")
        sys.exit(1)
    
    _ensure_playwright()
    
    print(f"\n🔐 正在打开 {config['name']}，请在浏览器中登录...", file=sys.stderr)
    print("   登录完成后，关闭浏览器窗口即可。\n", file=sys.stderr)
    
    with sync_playwright() as p:
        browser, ctx = create_browser_context(p, headless=False)
        page = ctx.new_page()
        
        try:
            page.goto(config["home_url"], wait_until="domcontentloaded", timeout=30000)
            
            # 等待用户关闭浏览器或按 Ctrl+C
            print("⏳ 等待登录... 登录完成后关闭浏览器窗口", file=sys.stderr)
            while True:
                try:
                    time.sleep(2)
                    page.title()  # 检查页面是否还存在
                except:
                    break
                    
        except KeyboardInterrupt:
            print("\n⏹ 停止等待", file=sys.stderr)
        
        # 保存 Cookie
        save_cookies(ctx, platform)
        browser.close()


# ========== 提取器 ==========

def extract_dianping_search(page):
    """大众点评搜索结果提取"""
    results = []
    time.sleep(2)
    
    # 检查是否需要验证
    title = page.title()
    if "验证" in title:
        print("⚠️ 大众点评要求验证，请先登录: python3 browser_fetch.py --login dianping", file=sys.stderr)
        return results
    
    # 搜索结果列表
    items = page.query_selector_all('[class*="shopInfo"], [class*="shop-info"], .shop-list li, [data-shopid]')
    
    if not items:
        # 尝试更通用的选择器
        items = page.query_selector_all('#shop-all-list li, .shop-list ul li')
    
    for item in items[:10]:
        try:
            name_el = item.query_selector('h4, .tit, [class*="shopName"], [class*="shop-name"], a.name')
            star_el = item.query_selector('[class*="star"], [class*="rating"]')
            price_el = item.query_selector('[class*="mean-price"], [class*="price"]')
            tag_el = item.query_selector('[class*="tag"], [class*="category"]')
            addr_el = item.query_selector('[class*="addr"], [class*="address"], [class*="region"]')
            link_el = item.query_selector('a[href*="shop"]')
            
            name = name_el.inner_text().strip() if name_el else ""
            if not name:
                continue
                
            results.append({
                "name": name,
                "rating": star_el.inner_text().strip() if star_el else "",
                "price": price_el.inner_text().strip() if price_el else "",
                "category": tag_el.inner_text().strip() if tag_el else "",
                "address": addr_el.inner_text().strip() if addr_el else "",
                "url": link_el.get_attribute("href") if link_el else "",
            })
        except:
            continue
    
    return results


def extract_dianping_shop(page):
    """大众点评店铺详情提取"""
    time.sleep(2)
    info = {}
    
    # 店名
    name_el = page.query_selector('h1, .shop-name, [class*="shopName"]')
    info["name"] = name_el.inner_text().strip() if name_el else ""
    
    # 评分
    star_el = page.query_selector('[class*="star"], [class*="score"]')
    info["rating"] = star_el.inner_text().strip() if star_el else ""
    
    # 人均
    price_el = page.query_selector('[class*="avgPrice"], [class*="price"]')
    info["avg_price"] = price_el.inner_text().strip() if price_el else ""
    
    # 地址
    addr_el = page.query_selector('[class*="address"], [itemprop="street-address"]')
    info["address"] = addr_el.inner_text().strip() if addr_el else ""
    
    # 评论摘要
    comments = []
    comment_els = page.query_selector_all('[class*="comment-item"], [class*="review"]')
    for c in comment_els[:5]:
        text = c.inner_text().strip()[:200]
        if text:
            comments.append(text)
    info["comments"] = comments
    
    # 菜品推荐
    dishes = []
    dish_els = page.query_selector_all('[class*="recommend-dish"], [class*="rec-tag"]')
    for d in dish_els[:10]:
        dishes.append(d.inner_text().strip())
    info["recommended_dishes"] = dishes
    
    return info


def extract_xiaohongshu_search(page):
    """小红书搜索结果提取"""
    results = []
    time.sleep(3)
    
    title = page.title()
    if "登录" in title or "验证" in title:
        print("⚠️ 小红书要求登录，请先登录: python3 browser_fetch.py --login xiaohongshu", file=sys.stderr)
        return results
    
    # 搜索结果卡片
    items = page.query_selector_all('[class*="note-item"], [class*="search-note"], section[class*="note"]')
    
    if not items:
        items = page.query_selector_all('a[href*="/explore/"]')
    
    for item in items[:10]:
        try:
            title_el = item.query_selector('[class*="title"], [class*="desc"], span')
            author_el = item.query_selector('[class*="author"], [class*="name"]')
            like_el = item.query_selector('[class*="like"], [class*="count"]')
            link_el = item.query_selector('a[href*="explore"]') or item
            
            note_title = title_el.inner_text().strip() if title_el else ""
            if not note_title:
                note_title = item.inner_text().strip()[:100]
            
            href = ""
            try:
                href = link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://www.xiaohongshu.com" + href
            except:
                pass
            
            results.append({
                "title": note_title,
                "author": author_el.inner_text().strip() if author_el else "",
                "likes": like_el.inner_text().strip() if like_el else "",
                "url": href,
            })
        except:
            continue
    
    return results


def extract_xiaohongshu_note(page):
    """小红书笔记详情提取"""
    time.sleep(3)
    info = {}
    
    title_el = page.query_selector('[class*="title"], h1')
    info["title"] = title_el.inner_text().strip() if title_el else ""
    
    # 正文
    content_el = page.query_selector('[class*="note-text"], [class*="content"], #detail-desc')
    info["content"] = content_el.inner_text().strip()[:2000] if content_el else ""
    
    # 作者
    author_el = page.query_selector('[class*="author-name"], [class*="username"]')
    info["author"] = author_el.inner_text().strip() if author_el else ""
    
    # 点赞/收藏
    like_el = page.query_selector('[class*="like-count"], [class*="like"]')
    info["likes"] = like_el.inner_text().strip() if like_el else ""
    
    # 评论
    comments = []
    comment_els = page.query_selector_all('[class*="comment-item"], [class*="comment-text"]')
    for c in comment_els[:5]:
        comments.append(c.inner_text().strip()[:200])
    info["comments"] = comments
    
    return info


def extract_generic(page):
    """通用网页提取"""
    time.sleep(2)
    
    # 提取主要文本内容
    for sel in ['article', 'main', '.content', '#content', '.article', '.post']:
        el = page.query_selector(sel)
        if el:
            return {"content": el.inner_text().strip()[:5000], "url": page.url}
    
    # 兜底：提取 body
    body = page.query_selector('body')
    text = body.inner_text().strip()[:5000] if body else ""
    return {"content": text, "url": page.url}


# ========== 平台检测 ==========

def detect_platform(url):
    """根据 URL 检测平台"""
    for key, config in PLATFORMS.items():
        if config["domain"] in url:
            return key
    return None


# ========== 搜索 ==========

def search_platform(query, platform, num=5, context=None, city=None):
    """在指定平台内搜索，登录失败自动切换到搜索引擎方案"""
    config = PLATFORMS.get(platform)
    if not config:
        print(f"❌ 不支持的平台: {platform}", file=sys.stderr)
        return []
    
    search_url = config["search_url"]
    
    # 大众点评需要城市 ID
    if platform == "dianping":
        city_id = config["default_city"]
        if city and city in config.get("cities", {}):
            city_id = config["cities"][city]
        search_url = search_url.format(city_id=city_id, query=urllib.parse.quote(query))
    else:
        search_url = search_url.format(query=urllib.parse.quote(query))
    
    print(f"🔍 在 {config['name']} 搜索: {query}", file=sys.stderr)
    print(f"   URL: {search_url}", file=sys.stderr)
    
    page = context.new_page()
    results = []
    need_fallback = False
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        
        # 检测登录重定向
        current_url = page.url
        page_text = page.inner_text("body")[:500]
        if ("login" in current_url or "pclogin" in current_url 
            or "登录后查看" in page_text or "请登录" in page_text[:100]
            or "扫码" in page_text[:200] and "搜索" not in page.title()):
            print(f"⚠️ 需要登录，自动切换到搜索引擎方案", file=sys.stderr)
            need_fallback = True
        else:
            # 滚动页面加载更多内容
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(1)
            
            if platform in ("dianping",):
                results = extract_dianping_search(page)
            elif platform in ("xiaohongshu", "xhs"):
                results = extract_xiaohongshu_search(page)
            else:
                text = page.inner_text("body")[:3000]
                results = [{"content": text, "url": search_url}]
        
    except Exception as e:
        print(f"⚠️ 直接搜索失败: {e}", file=sys.stderr)
        need_fallback = True
    finally:
        page.close()
    
    # 无结果或需要登录时，回退到搜索引擎
    if need_fallback or not results:
        print(f"🔄 使用搜索引擎间接搜索 (site:{config['domain']})", file=sys.stderr)
        results = search_via_engine(query, config["domain"], num, context, city)
    
    return results[:num]


def search_via_engine(query, site_domain, num=5, context=None, city=None):
    """通过搜索引擎间接搜索平台内容（不需要登录）"""
    # 构建搜索引擎查询
    search_query = f"site:{site_domain} {query}"
    if city:
        search_query += f" {city}"
    
    encoded_q = urllib.parse.quote(search_query)
    
    # 优先 DuckDuckGo（无 CAPTCHA），然后 Google
    engines = [
        ("DuckDuckGo", f"https://duckduckgo.com/?q={encoded_q}"),
        ("Google", f"https://www.google.com/search?q={encoded_q}"),
    ]
    
    for engine_name, engine_url in engines:
        print(f"   🌐 {engine_name}: {search_query}", file=sys.stderr)
        
        page = context.new_page()
        try:
            page.goto(engine_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
            
            # 滚动加载更多
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(1)
            
            results = _extract_search_engine_results(page, engine_name, site_domain)
            
            if results:
                print(f"   ✅ {engine_name} 返回 {len(results)} 条结果", file=sys.stderr)
                page.close()
                return results[:num]
            
        except Exception as e:
            print(f"   ⚠️ {engine_name} 失败: {e}", file=sys.stderr)
        finally:
            page.close()
    
    return []


def _extract_search_engine_results(page, engine, site_domain):
    """从搜索引擎结果页提取数据"""
    results = []
    
    try:
        if engine == "DuckDuckGo":
            # DuckDuckGo 结果提取
            items = page.query_selector_all("article[data-testid='result']")
            if not items:
                items = page.query_selector_all(".result, .results .result__body, .nrn-react-div")
            
            for item in items:
                try:
                    # 标题
                    title_el = item.query_selector("h2 a, a[data-testid='result-title-a']")
                    title = title_el.inner_text().strip() if title_el else ""
                    
                    # URL
                    href = title_el.get_attribute("href") if title_el else ""
                    
                    # 摘要
                    snippet_el = item.query_selector("span[data-testid='result-snippet'], .result__snippet")
                    snippet = snippet_el.inner_text().strip() if snippet_el else ""
                    
                    if title and site_domain in (href or ""):
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "source": "search_engine",
                        })
                except:
                    continue
        
        elif engine == "Google":
            # Google 结果提取
            items = page.query_selector_all("div.g, div[data-sokoban-container]")
            
            for item in items:
                try:
                    title_el = item.query_selector("h3")
                    title = title_el.inner_text().strip() if title_el else ""
                    
                    link_el = item.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""
                    
                    snippet_el = item.query_selector("div[data-sncf], .VwiC3b, span.st")
                    snippet = snippet_el.inner_text().strip() if snippet_el else ""
                    
                    if title and site_domain in (href or ""):
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "source": "search_engine",
                        })
                except:
                    continue
        
        # 通用 fallback — 纯文本提取
        if not results:
            body_text = page.inner_text("body")
            # 提取所有包含目标域名的链接
            links = page.query_selector_all(f"a[href*='{site_domain}']")
            for link in links[:20]:
                try:
                    title = link.inner_text().strip()
                    href = link.get_attribute("href")
                    if title and len(title) > 3 and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": "",
                            "source": "search_engine",
                        })
                except:
                    continue
    
    except Exception as e:
        print(f"   ⚠️ 提取搜索结果失败: {e}", file=sys.stderr)
    
    return results


# ========== 抓取 URL ==========

def fetch_url(url, context):
    """用浏览器抓取指定 URL"""
    platform = detect_platform(url)
    print(f"📖 抓取: {url}", file=sys.stderr)
    
    page = context.new_page()
    result = {}
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        
        result["url"] = url
        result["title"] = page.title()
        
        if platform == "dianping":
            result["data"] = extract_dianping_shop(page)
        elif platform in ("xiaohongshu", "xhs"):
            result["data"] = extract_xiaohongshu_note(page)
        else:
            result["data"] = extract_generic(page)
            
    except Exception as e:
        result["error"] = str(e)
        print(f"⚠️ 抓取失败: {e}", file=sys.stderr)
    finally:
        page.close()
    
    return result


# ========== 输出格式化 ==========

def print_results(data, as_json=False):
    """格式化打印结果"""
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    
    if isinstance(data, list):
        if not data:
            print("\n❌ 未找到结果")
            return
        print(f"\n━━━ 找到 {len(data)} 条结果 ━━━\n")
        for i, item in enumerate(data, 1):
            if "name" in item:
                # 大众点评格式
                print(f"[{i}] 📍 {item['name']}")
                if item.get("rating"):
                    print(f"    ⭐ {item['rating']}")
                if item.get("price"):
                    print(f"    💰 {item['price']}")
                if item.get("category"):
                    print(f"    🏷️ {item['category']}")
                if item.get("address"):
                    print(f"    📍 {item['address']}")
                if item.get("url"):
                    href = item["url"]
                    if not href.startswith("http"):
                        href = "https://www.dianping.com" + href
                    print(f"    🔗 {href}")
            elif "title" in item:
                # 小红书格式
                print(f"[{i}] 📝 {item['title']}")
                if item.get("author"):
                    print(f"    👤 {item['author']}")
                if item.get("likes"):
                    print(f"    ❤️ {item['likes']}")
                if item.get("url"):
                    print(f"    🔗 {item['url']}")
            elif "content" in item:
                # 通用格式
                print(f"[{i}] {item.get('content', '')[:200]}")
            print()
    
    elif isinstance(data, dict):
        if "data" in data:
            info = data["data"]
            print(f"\n━━━ {data.get('title', '')} ━━━\n")
            for k, v in info.items():
                if isinstance(v, list):
                    print(f"  {k}:")
                    for item in v:
                        print(f"    - {item}")
                else:
                    print(f"  {k}: {v}")
        elif "error" in data:
            print(f"\n❌ 错误: {data['error']}")
        else:
            for k, v in data.items():
                print(f"  {k}: {v}")


# ========== 主程序 ==========

def main():
    parser = argparse.ArgumentParser(
        description="浏览器数据抓取 — 直接访问大众点评/小红书等平台",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 搜索大众点评
  python3 browser_fetch.py --search "外滩餐厅" --site dianping

  # 搜索小红书
  python3 browser_fetch.py --search "上海美食推荐" --site xiaohongshu

  # 抓取具体页面
  python3 browser_fetch.py "https://www.dianping.com/shop/123456"

  # 首次使用需登录（会弹出浏览器窗口）
  python3 browser_fetch.py --login dianping
        """
    )
    parser.add_argument("url", nargs="?", help="要抓取的 URL")
    parser.add_argument("--search", help="搜索关键词")
    parser.add_argument("--site", choices=list(PLATFORMS.keys()), help="搜索平台")
    parser.add_argument("--city", help="城市（仅大众点评，如：上海/北京/广州）")
    parser.add_argument("--num", "-n", type=int, default=5, help="结果数量 (默认 5)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--mobile", action="store_true", help="模拟手机访问")
    parser.add_argument("--login", metavar="PLATFORM", choices=list(PLATFORMS.keys()),
                        help="登录平台保存 Cookie（首次使用）")
    
    args = parser.parse_args()
    
    # 模式0: 登录
    if args.login:
        login_platform(args.login)
        return
    
    if not args.url and not args.search:
        parser.print_help()
        return
    
    _ensure_playwright()
    
    # 自动检测 CDP 模式
    cdp_available = _check_cdp_port() is not None
    if cdp_available:
        print("🔗 检测到 Chrome Debug 端口，使用 CDP 模式", file=sys.stderr)
    
    with sync_playwright() as p:
        browser, ctx = create_browser_context(p, headless=True, mobile=args.mobile, use_cdp=cdp_available)
        
        # 非 CDP 模式下加载已保存的 Cookie
        if not cdp_available:
            if args.url:
                platform = detect_platform(args.url)
                if platform:
                    load_cookies(ctx, platform)
            elif args.site:
                load_cookies(ctx, args.site)
        
        try:
            if args.search and args.site:
                # 模式1: 平台站内搜索
                results = search_platform(args.search, args.site, args.num, ctx, args.city)
                print_results(results, args.json)
                
            elif args.search:
                # 没指定 site，提示用户
                print("请指定搜索平台，例如: --site dianping 或 --site xiaohongshu")
                parser.print_help()
                
            elif args.url:
                # 模式2: 直接抓取 URL
                result = fetch_url(args.url, ctx)
                print_results(result, args.json)
                
        finally:
            if not cdp_available:
                ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
