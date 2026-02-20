#!/usr/bin/env python3
"""
快速 Cookie 导出工具 — 从 Chrome DevTools 或剪贴板获取 Cookie
绕过 Playwright 非 headless 模式的 macOS 权限限制

用法:
  python3 quick_cookie_export.py dianping
  python3 quick_cookie_export.py xiaohongshu

支持两种模式:
  1. 自动模式: 通过 AppleScript 从 Chrome 当前页面获取 document.cookie
  2. 手动模式: 用户从 DevTools Console 复制 Cookie 粘贴到终端
"""

import json
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPENCLAW_ROOT = os.environ.get("OPENCLAW_HOME",
    os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
COOKIE_DIR = os.path.join(OPENCLAW_ROOT, ".openclaw", "cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)

PLATFORMS = {
    "dianping": {
        "name": "大众点评",
        "domain": ".dianping.com",
        "url": "https://www.dianping.com",
        "match": "dianping.com",
    },
    "xiaohongshu": {
        "name": "小红书",
        "domain": ".xiaohongshu.com",
        "url": "https://www.xiaohongshu.com",
        "match": "xiaohongshu.com",
    },
    "xhs": {
        "name": "小红书",
        "domain": ".xiaohongshu.com",
        "url": "https://www.xiaohongshu.com",
        "match": "xiaohongshu.com",
    },
    "zhihu": {
        "name": "知乎",
        "domain": ".zhihu.com",
        "url": "https://www.zhihu.com",
        "match": "zhihu.com",
    },
}


def parse_cookie_string(cookie_str, domain):
    """将 document.cookie 字符串解析为 Playwright 格式"""
    cookies = []
    for item in cookie_str.strip().split("; "):
        if "=" in item:
            name, value = item.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name and value:
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                })
    return cookies


def try_applescript_export(platform_config):
    """通过 AppleScript 从 Chrome 获取 Cookie（自动模式）"""
    match_domain = platform_config["match"]
    
    try:
        # 先检查 Chrome 是否在运行
        check = subprocess.run(
            ["pgrep", "-x", "Google Chrome"],
            capture_output=True, text=True, timeout=3
        )
        if check.returncode != 0:
            print("⚠️ Chrome 未运行", file=sys.stderr)
            return None
        
        # 通过 AppleScript 获取 Cookie
        script = f'''
        tell application "Google Chrome"
            set targetTab to missing value
            repeat with w in (every window)
                repeat with t in (every tab of w)
                    if URL of t contains "{match_domain}" then
                        set targetTab to t
                        exit repeat
                    end if
                end repeat
                if targetTab is not missing value then exit repeat
            end repeat
            
            if targetTab is missing value then
                return "TAB_NOT_FOUND"
            end if
            
            set cookieStr to execute targetTab javascript "document.cookie"
            return cookieStr
        end tell
        '''
        
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            print(f"⚠️ AppleScript 执行失败: {result.stderr.strip()}", file=sys.stderr)
            return None
        
        output = result.stdout.strip()
        
        if output == "TAB_NOT_FOUND":
            print(f"⚠️ Chrome 中没有找到 {platform_config['name']} 的标签页", file=sys.stderr)
            return None
        
        if not output or output == "missing value":
            print("⚠️ 获取到空 Cookie（可能未登录）", file=sys.stderr)
            return None
        
        return output
        
    except subprocess.TimeoutExpired:
        print("⚠️ AppleScript 超时", file=sys.stderr)
        return None
    except Exception as e:
        print(f"⚠️ AppleScript 失败: {e}", file=sys.stderr)
        return None


def try_clipboard_export():
    """从剪贴板获取 Cookie"""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    return None


def manual_paste_export():
    """手动粘贴 Cookie"""
    print("\n请粘贴 Cookie 字符串（粘贴后按 Enter）:", file=sys.stderr)
    try:
        cookie_str = input()
        return cookie_str.strip()
    except (EOFError, KeyboardInterrupt):
        return None


def save_cookies(cookies, platform):
    """保存 Cookie 到文件"""
    # 标准化平台名
    save_name = "xiaohongshu" if platform == "xhs" else platform
    path = os.path.join(COOKIE_DIR, f"{save_name}_cookies.json")
    with open(path, "w") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存 {len(cookies)} 条 Cookie → {path}", file=sys.stderr)
    return path


def main():
    if len(sys.argv) < 2:
        print("用法: python3 quick_cookie_export.py <平台名>")
        print(f"支持: {', '.join(PLATFORMS.keys())}")
        print("\n示例:")
        print("  python3 quick_cookie_export.py dianping")
        print("  python3 quick_cookie_export.py xiaohongshu")
        sys.exit(0)
    
    platform = sys.argv[1].lower()
    if platform not in PLATFORMS:
        print(f"❌ 不支持的平台: {platform}")
        print(f"支持: {', '.join(PLATFORMS.keys())}")
        sys.exit(1)
    
    config = PLATFORMS[platform]
    domain = config["domain"]
    
    print(f"\n🔐 导出 {config['name']} Cookie", file=sys.stderr)
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━", file=sys.stderr)
    
    # 方式1: 自动模式（AppleScript）
    print(f"\n📡 尝试自动从 Chrome 获取...", file=sys.stderr)
    cookie_str = try_applescript_export(config)
    
    if cookie_str:
        cookies = parse_cookie_string(cookie_str, domain)
        if cookies:
            print(f"✅ 自动获取成功！({len(cookies)} 条)", file=sys.stderr)
            save_cookies(cookies, platform)
            return
    
    # 方式2: 引导手动操作
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"📋 需要手动导出（自动模式不可用）", file=sys.stderr)
    print(f"{'='*50}", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"请按以下步骤操作:", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"  1. 在 Chrome 中打开 {config['url']}", file=sys.stderr)
    print(f"  2. 确保已登录", file=sys.stderr)
    print(f"  3. 按 F12 (或 Cmd+Option+I) 打开 DevTools", file=sys.stderr)
    print(f"  4. 切换到 Console 标签", file=sys.stderr)
    print(f"  5. 粘贴并运行以下代码:", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f'     copy(document.cookie)', file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"  6. 这会将 Cookie 复制到剪贴板", file=sys.stderr)
    print(f"", file=sys.stderr)
    
    # 等待用户操作
    print(f"完成上述步骤后，选择导入方式:", file=sys.stderr)
    print(f"  [1] 从剪贴板自动读取 (推荐)", file=sys.stderr)
    print(f"  [2] 手动粘贴到终端", file=sys.stderr)
    print(f"", file=sys.stderr)
    
    choice = input("请选择 [1/2]: ").strip()
    
    cookie_str = None
    if choice == "2":
        cookie_str = manual_paste_export()
    else:
        # 默认从剪贴板读取
        print("\n📋 正在从剪贴板读取...", file=sys.stderr)
        cookie_str = try_clipboard_export()
        if not cookie_str:
            print("⚠️ 剪贴板为空，请手动粘贴", file=sys.stderr)
            cookie_str = manual_paste_export()
    
    if not cookie_str:
        print("❌ 未获取到 Cookie", file=sys.stderr)
        sys.exit(1)
    
    cookies = parse_cookie_string(cookie_str, domain)
    if not cookies:
        print("❌ Cookie 解析失败（格式不正确）", file=sys.stderr)
        sys.exit(1)
    
    save_cookies(cookies, platform)
    print(f"\n🎉 接下来可以使用 browser_fetch.py 搜索 {config['name']} 了！", file=sys.stderr)


if __name__ == "__main__":
    main()
