#!/usr/bin/env python3
"""
CDP Cookie 导出工具 — 通过 Chrome Debug 端口导出完整 Cookie
连接 Chrome 远程调试端口(9222)，获取所有平台 Cookie（含 httpOnly）

用法:
  python3 cdp_cookie_export.py              # 导出所有平台 Cookie
  python3 cdp_cookie_export.py dianping     # 仅导出大众点评
  python3 cdp_cookie_export.py xiaohongshu  # 仅导出小红书

前提:
  Chrome 需以 --remote-debugging-port=9222 启动
  双击 "启动Chrome调试模式.command" 即可
"""

import json
import os
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_ROOT = os.environ.get("OPENCLAW_HOME",
    os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
COOKIE_DIR = os.path.join(OPENCLAW_ROOT, ".openclaw", "cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)

CDP_PORT = int(os.environ.get("CDP_PORT", "9222"))

PLATFORMS = {
    "dianping": {
        "name": "大众点评",
        "domains": [".dianping.com", ".meituan.com"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "domains": [".xiaohongshu.com"],
    },
    "zhihu": {
        "name": "知乎",
        "domains": [".zhihu.com"],
    },
    "weibo": {
        "name": "微博",
        "domains": [".weibo.com", ".weibo.cn"],
    },
    "bilibili": {
        "name": "B站",
        "domains": [".bilibili.com"],
    },
}


def check_cdp_port(port):
    """检查 CDP 端口是否可用"""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/version")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data
    except Exception:
        return None


def get_all_cookies_via_playwright(port):
    """通过 Playwright CDP 连接获取所有 Cookie"""
    # 确保 TMPDIR 可用
    pw_tmp = os.path.join(OPENCLAW_ROOT, ".openclaw", "pw_tmp")
    os.makedirs(pw_tmp, exist_ok=True)
    os.environ["TMPDIR"] = pw_tmp
    
    # 设置 Playwright 浏览器路径
    venv_browsers = os.path.join(SCRIPT_DIR, "..", ".venv", "browsers")
    if os.path.exists(venv_browsers):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.abspath(venv_browsers))
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright 未安装", file=sys.stderr)
        print("   运行: .venv/bin/pip install playwright", file=sys.stderr)
        return None
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            print(f"✅ 已连接 Chrome Debug 端口 {port}", file=sys.stderr)
            
            # 获取所有上下文
            all_cookies = []
            contexts = browser.contexts
            
            if not contexts:
                print("⚠️ 没有找到浏览器上下文", file=sys.stderr)
                return []
            
            for ctx in contexts:
                cookies = ctx.cookies()
                all_cookies.extend(cookies)
            
            print(f"📦 获取到 {len(all_cookies)} 条 Cookie", file=sys.stderr)
            
            # 不要关闭 browser —— 它是通过 CDP 连接的用户 Chrome
            browser.close()
            return all_cookies
            
        except Exception as e:
            print(f"❌ CDP 连接失败: {e}", file=sys.stderr)
            return None


def filter_cookies_by_platform(all_cookies, platform):
    """按平台过滤 Cookie"""
    config = PLATFORMS.get(platform)
    if not config:
        return []
    
    filtered = []
    for cookie in all_cookies:
        domain = cookie.get("domain", "")
        for target_domain in config["domains"]:
            if domain.endswith(target_domain.lstrip(".")):
                # 转换为 Playwright 兼容格式
                c = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": cookie.get("domain", target_domain),
                    "path": cookie.get("path", "/"),
                }
                # 保留可选字段
                if cookie.get("expires", -1) > 0:
                    c["expires"] = cookie["expires"]
                if cookie.get("httpOnly"):
                    c["httpOnly"] = True
                if cookie.get("secure"):
                    c["secure"] = True
                if cookie.get("sameSite"):
                    c["sameSite"] = cookie["sameSite"]
                filtered.append(c)
                break
    
    return filtered


def save_platform_cookies(cookies, platform):
    """保存平台 Cookie 到文件"""
    save_name = "xiaohongshu" if platform == "xhs" else platform
    path = os.path.join(COOKIE_DIR, f"{save_name}_cookies.json")
    with open(path, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def main():
    target_platform = None
    if len(sys.argv) > 1:
        target_platform = sys.argv[1].lower()
        if target_platform == "xhs":
            target_platform = "xiaohongshu"
        if target_platform not in PLATFORMS:
            print(f"❌ 不支持的平台: {target_platform}")
            print(f"支持: {', '.join(PLATFORMS.keys())}")
            sys.exit(1)
    
    print("\n🔐 CDP Cookie 导出工具", file=sys.stderr)
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    
    # 检查 CDP 端口
    version = check_cdp_port(CDP_PORT)
    if not version:
        print(f"\n❌ Chrome Debug 端口 {CDP_PORT} 未就绪", file=sys.stderr)
        print("   请先双击运行 '启动Chrome调试模式.command'", file=sys.stderr)
        print(f"   或手动启动: open -a 'Google Chrome' --args --remote-debugging-port={CDP_PORT}", file=sys.stderr)
        sys.exit(1)
    
    print(f"🌐 Chrome 版本: {version.get('Browser', 'unknown')}", file=sys.stderr)
    
    # 获取所有 Cookie
    all_cookies = get_all_cookies_via_playwright(CDP_PORT)
    if all_cookies is None:
        sys.exit(1)
    
    # 按平台分类保存
    platforms_to_export = [target_platform] if target_platform else list(PLATFORMS.keys())
    
    results = {}
    for platform in platforms_to_export:
        config = PLATFORMS[platform]
        filtered = filter_cookies_by_platform(all_cookies, platform)
        
        if filtered:
            path = save_platform_cookies(filtered, platform)
            results[platform] = {"count": len(filtered), "path": path}
            print(f"  ✅ {config['name']}: {len(filtered)} 条 Cookie → {path}", file=sys.stderr)
        else:
            print(f"  ⚠️ {config['name']}: 未找到 Cookie（可能未登录）", file=sys.stderr)
    
    # 输出结果 JSON
    print("\n" + json.dumps(results, ensure_ascii=False, indent=2))
    
    if results:
        print(f"\n🎉 Cookie 导出完成！可以用 browser_fetch.py 抓取数据了", file=sys.stderr)
    else:
        print(f"\n⚠️ 未找到任何平台的 Cookie", file=sys.stderr)
        print(f"   请在 Chrome 中登录目标网站后重试", file=sys.stderr)


if __name__ == "__main__":
    main()
