#!/usr/bin/env python3
"""
Cookie 导入工具 — 从浏览器 document.cookie 或 JSON 格式导入
支持两种输入格式:
  1. document.cookie 格式: "name1=value1; name2=value2; ..."
  2. JSON 数组格式 (EditThisCookie 等扩展导出)

用法:
  python3 import_cookies.py dianping     # 交互式导入大众点评 Cookie
  python3 import_cookies.py xiaohongshu  # 交互式导入小红书 Cookie
  echo "cookie_string" | python3 import_cookies.py dianping --stdin
"""

import argparse
import json
import os
import sys

OPENCLAW_HOME = os.environ.get("OPENCLAW_HOME", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
COOKIE_DIR = os.path.join(OPENCLAW_HOME, ".openclaw", "cookies")

PLATFORMS = {
    "dianping": {
        "name": "大众点评",
        "domain": ".dianping.com",
        "test_url": "https://www.dianping.com",
        "extra_domains": [".meituan.com"],
    },
    "xiaohongshu": {
        "name": "小红书",
        "domain": ".xiaohongshu.com",
        "test_url": "https://www.xiaohongshu.com",
    },
    "meituan": {
        "name": "美团",
        "domain": ".meituan.com",
        "test_url": "https://www.meituan.com",
    },
}


def parse_cookie_string(cookie_str, domain):
    """解析 document.cookie 格式的字符串"""
    cookies = []
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        name, _, value = item.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
            })
    return cookies


def parse_json_cookies(json_str):
    """解析 JSON 格式的 Cookie (如 EditThisCookie 导出)"""
    data = json.loads(json_str)
    if not isinstance(data, list):
        data = [data]
    
    cookies = []
    for item in data:
        c = {
            "name": item.get("name", ""),
            "value": item.get("value", ""),
            "domain": item.get("domain", ""),
            "path": item.get("path", "/"),
        }
        if item.get("expirationDate"):
            c["expires"] = item["expirationDate"]
        if item.get("httpOnly"):
            c["httpOnly"] = True
        if item.get("secure"):
            c["secure"] = True
        if item.get("sameSite"):
            c["sameSite"] = item["sameSite"]
        cookies.append(c)
    return cookies


def save_cookies(platform, cookies):
    """保存 Cookie 到文件"""
    os.makedirs(COOKIE_DIR, exist_ok=True)
    path = os.path.join(COOKIE_DIR, f"{platform}_cookies.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Cookie 导入工具")
    parser.add_argument("platform", choices=list(PLATFORMS.keys()), help="目标平台")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取 Cookie")
    parser.add_argument("--cookie", type=str, help="直接传入 Cookie 字符串")
    args = parser.parse_args()

    platform_info = PLATFORMS[args.platform]
    domain = platform_info["domain"]

    if args.cookie:
        raw = args.cookie
    elif args.stdin:
        raw = sys.stdin.read().strip()
    else:
        print(f"\n📋 {platform_info['name']} Cookie 导入", file=sys.stderr)
        print(f"{'='*50}", file=sys.stderr)
        print(f"\n操作步骤:", file=sys.stderr)
        print(f"  1. 在 Chrome 中打开 {platform_info['test_url']} 并确保已登录", file=sys.stderr)
        print(f"  2. 按 F12 打开开发者工具 → Console 标签", file=sys.stderr)
        print(f"  3. 输入: document.cookie", file=sys.stderr)
        print(f"  4. 复制输出结果", file=sys.stderr)
        print(f"  5. 粘贴到下方（粘贴后按 Enter 再按 Ctrl+D 结束）\n", file=sys.stderr)
        print(f"请粘贴 Cookie 字符串 ↓", file=sys.stderr)
        
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        raw = "\n".join(lines).strip()

    if not raw:
        print("❌ 未提供 Cookie 数据", file=sys.stderr)
        sys.exit(1)

    # 尝试自动检测格式
    raw = raw.strip().strip("'\"")
    
    if raw.startswith("[") or raw.startswith("{"):
        cookies = parse_json_cookies(raw)
        fmt = "JSON"
    else:
        cookies = parse_cookie_string(raw, domain)
        fmt = "document.cookie"

    if not cookies:
        print("❌ 未解析到任何 Cookie", file=sys.stderr)
        sys.exit(1)

    path = save_cookies(args.platform, cookies)
    print(f"\n✅ 已保存 {len(cookies)} 条 {platform_info['name']} Cookie ({fmt} 格式)", file=sys.stderr)
    print(f"   → {path}", file=sys.stderr)
    
    # 输出 JSON 到 stdout
    print(json.dumps({"platform": args.platform, "count": len(cookies), "path": path}))


if __name__ == "__main__":
    main()
