#!/usr/bin/env python3
"""
从用户 Chrome 浏览器导出指定网站的 Cookie
使用 Chrome DevTools Protocol (CDP) 远程调试接口

用法:
  1. 确保 Chrome 已打开并登录了目标网站
  2. 运行: python3 export_cookies.py dianping
  3. Cookie 自动保存到 .openclaw/cookies/

支持平台: dianping, xiaohongshu, zhihu, weibo, bilibili
"""

import json
import os
import sys
import subprocess
import http.client
import urllib.request
import ssl
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_ROOT = os.environ.get("OPENCLAW_HOME", 
    os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
COOKIE_DIR = os.path.join(OPENCLAW_ROOT, ".openclaw", "cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)

PLATFORM_DOMAINS = {
    "dianping": [".dianping.com"],
    "xiaohongshu": [".xiaohongshu.com"],
    "xhs": [".xiaohongshu.com"],
    "zhihu": [".zhihu.com"],
    "weibo": [".weibo.com", ".weibo.cn"],
    "bilibili": [".bilibili.com"],
}

PLATFORM_URLS = {
    "dianping": "https://www.dianping.com",
    "xiaohongshu": "https://www.xiaohongshu.com",
    "xhs": "https://www.xiaohongshu.com", 
    "zhihu": "https://www.zhihu.com",
    "weibo": "https://weibo.com",
    "bilibili": "https://www.bilibili.com",
}


def open_chrome_with_debug():
    """用调试端口打开 Chrome"""
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    debug_port = 9222
    
    # 检查 Chrome 是否已经以调试模式运行
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json/version")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            print(f"✅ Chrome 调试端口已就绪 (版本: {data.get('Browser', 'unknown')})", file=sys.stderr)
            return debug_port
    except:
        pass
    
    print("⚠️ Chrome 未以调试模式启动。", file=sys.stderr)
    print("", file=sys.stderr)
    print("请关闭 Chrome，然后运行以下命令重新打开:", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f'  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={debug_port} &', file=sys.stderr)
    print(f"", file=sys.stderr)
    print("或者创建一个快捷方式:", file=sys.stderr)
    print(f'  open -a "Google Chrome" --args --remote-debugging-port={debug_port}', file=sys.stderr)
    print("", file=sys.stderr)
    return None


def get_cookies_via_cdp(debug_port, domains):
    """通过 CDP 获取指定域名的 Cookie"""
    try:
        # 获取页面列表
        req = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pages = json.loads(resp.read())
        
        if not pages:
            print("❌ Chrome 没有打开任何页面", file=sys.stderr)
            return None
        
        # 使用第一个页面的 WebSocket 连接
        ws_url = pages[0].get("webSocketDebuggerUrl")
        if not ws_url:
            print("❌ 无法获取 WebSocket URL", file=sys.stderr)
            return None
        
        # 用 HTTP 接口获取所有 Cookie
        # Chrome DevTools Protocol 的 /json/protocol 不直接支持获取 cookie
        # 需要通过 Network.getAllCookies 命令
        
        # 简单方式：通过 JavaScript 在目标域名页面获取 cookie
        # 但这只能获取非 httpOnly 的 cookie
        
        # 更好的方式：通过 CDP WebSocket
        # 但这需要 websocket 库
        
        # 最简方式：通过 Chrome 的 sqlite 数据库读取（macOS 需要解密）
        # 这也很复杂
        
        # 妥协方案：通过启动 Chrome 页面执行 JS 获取可访问的 cookie
        print(f"📋 获取到 {len(pages)} 个 Chrome 标签页", file=sys.stderr)
        
        # 查找目标域名的标签页
        target_page = None
        for p in pages:
            page_url = p.get("url", "")
            for domain in domains:
                if domain.lstrip(".") in page_url:
                    target_page = p
                    break
            if target_page:
                break
        
        if not target_page:
            print(f"⚠️ 没有找到目标网站的标签页，请先在 Chrome 中打开并登录目标网站", file=sys.stderr)
            return None
        
        print(f"📄 找到目标页面: {target_page.get('title', '')} ({target_page.get('url', '')})", file=sys.stderr)
        
        # 通过 CDP HTTP 接口执行 JavaScript 获取 document.cookie
        # 注意：这只能获取非 httpOnly 的 cookie
        page_id = target_page["id"]
        
        # 使用 /json/protocol 发送 CDP 命令
        # 实际上需要 WebSocket，先用简单的 JS evaluate
        
        return target_page
        
    except Exception as e:
        print(f"❌ CDP 连接失败: {e}", file=sys.stderr)
        return None


def export_cookies_js_method(debug_port, platform):
    """通过在 Chrome 中执行 JS 获取 Cookie（简单但有限）"""
    domains = PLATFORM_DOMAINS.get(platform, [])
    url = PLATFORM_URLS.get(platform)
    
    try:
        # 获取页面列表
        req = urllib.request.Request(f"http://127.0.0.1:{debug_port}/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pages = json.loads(resp.read())
        
        # 查找目标页面
        target = None
        for p in pages:
            page_url = p.get("url", "")
            for domain in domains:
                if domain.lstrip(".") in page_url:
                    target = p
                    break
        
        if not target:
            print(f"\n⚠️ Chrome 中没有打开 {platform} 的页面", file=sys.stderr)
            print(f"   请先在 Chrome 中打开 {url} 并登录", file=sys.stderr)
            print(f"   然后重新运行此脚本\n", file=sys.stderr)
            return False
        
        print(f"✅ 找到 {platform} 页面: {target.get('title', '')}", file=sys.stderr)
        
        # 通过 CDP WebSocket 获取完整 Cookie（包括 httpOnly）
        # 需要用 websocket 连接
        ws_url = target.get("webSocketDebuggerUrl")
        
        # 尝试简单方式：直接用 document.cookie
        # CDP evaluate 需要 WebSocket，改用 subprocess + osascript
        
        # 用 osascript 从 Chrome 获取 cookie
        result = subprocess.run([
            "osascript", "-e",
            f'''
            tell application "Google Chrome"
                set targetTab to missing value
                repeat with w in (every window)
                    repeat with t in (every tab of w)
                        if URL of t contains "{domains[0].lstrip('.')}" then
                            set targetTab to t
                            exit repeat
                        end if
                    end repeat
                    if targetTab is not missing value then exit repeat
                end repeat
                
                if targetTab is missing value then
                    return "ERROR: No tab found"
                end if
                
                set active tab of (window 1) to targetTab
                set cookieStr to execute targetTab javascript "document.cookie"
                return cookieStr
            end tell
            '''
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0 or "ERROR" in result.stdout:
            print(f"⚠️ 无法获取 Cookie: {result.stderr or result.stdout}", file=sys.stderr)
            return False
        
        cookie_str = result.stdout.strip()
        if not cookie_str:
            print("⚠️ Cookie 为空，可能未登录", file=sys.stderr)
            return False
        
        # 解析 cookie 字符串为 Playwright 格式
        cookies = []
        for item in cookie_str.split("; "):
            if "=" in item:
                name, value = item.split("=", 1)
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": domains[0],
                    "path": "/",
                })
        
        # 保存
        cookie_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.json")
        with open(cookie_path, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已导出 {len(cookies)} 条 Cookie → {cookie_path}", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"❌ 导出失败: {e}", file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python3 export_cookies.py <平台名>")
        print("支持: dianping, xiaohongshu, zhihu, weibo, bilibili")
        print("\n步骤:")
        print("  1. 在 Chrome 中打开并登录目标网站")
        print("  2. 运行: python3 export_cookies.py dianping")
        print("  3. Cookie 自动保存，browser_fetch.py 会自动使用")
        sys.exit(0)
    
    platform = sys.argv[1].lower()
    
    if platform not in PLATFORM_DOMAINS:
        print(f"❌ 不支持的平台: {platform}")
        print(f"支持: {', '.join(PLATFORM_DOMAINS.keys())}")
        sys.exit(1)
    
    url = PLATFORM_URLS.get(platform)
    domains = PLATFORM_DOMAINS.get(platform)
    
    print(f"\n🔐 导出 {platform} Cookie", file=sys.stderr)
    print(f"   请确保已在 Chrome 中打开并登录 {url}\n", file=sys.stderr)
    
    # 方式1: 通过 AppleScript 直接从 Chrome 获取
    success = export_cookies_js_method(9222, platform)
    
    if not success:
        # 方式2: 提示用户手动操作
        print("\n" + "="*50, file=sys.stderr)
        print("📋 手动导出方法:", file=sys.stderr)
        print(f"  1. 在 Chrome 中打开 {url}", file=sys.stderr)
        print(f"  2. 按 F12 打开开发者工具", file=sys.stderr)
        print(f"  3. 切换到 Console 标签", file=sys.stderr)
        print(f"  4. 输入: document.cookie", file=sys.stderr)
        print(f"  5. 复制输出的 Cookie 字符串", file=sys.stderr)
        print(f"  6. 运行: python3 export_cookies.py {platform} --paste", file=sys.stderr)
        print("="*50, file=sys.stderr)
        
        if len(sys.argv) > 2 and sys.argv[2] == "--paste":
            print("\n请粘贴 Cookie 字符串:", file=sys.stderr)
            cookie_str = input()
            cookies = []
            for item in cookie_str.split("; "):
                if "=" in item:
                    name, value = item.split("=", 1)
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": domains[0],
                        "path": "/",
                    })
            
            cookie_path = os.path.join(COOKIE_DIR, f"{platform}_cookies.json")
            with open(cookie_path, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"✅ 已保存 {len(cookies)} 条 Cookie → {cookie_path}")


if __name__ == "__main__":
    main()
