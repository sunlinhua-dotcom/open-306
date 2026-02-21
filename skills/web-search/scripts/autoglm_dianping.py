#!/usr/bin/env python3
"""
AutoGLM 大众点评数据抓取工具

通过 Android 模拟器 + 智谱 AutoGLM API 自动操作大众点评 APP，抓取结构化数据。

用法:
    python3 autoglm_dianping.py "外滩餐厅" --city 上海 --count 10
    python3 autoglm_dianping.py "火锅" --city 北京 --count 20 --output result.json
"""

import subprocess
import base64
import json
import os
import sys
import time
import re
import argparse
from pathlib import Path
from typing import Optional

# ========== 配置 ==========
ANDROID_HOME = os.environ.get("ANDROID_HOME", "/Users/linhuasun/Desktop/OPENCLAW/.openclaw/android-sdk")
ADB = os.path.join(ANDROID_HOME, "platform-tools", "adb")
ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")
AUTOGLM_MODEL = "autoglm-phone"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
SCREENSHOT_DIR = os.path.join(ANDROID_HOME, "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# ========== ADB 工具 ==========
class ADBController:
    """ADB 设备控制器"""

    def __init__(self, adb_path: str = ADB):
        self.adb = adb_path

    def _run(self, *args, timeout=10) -> str:
        cmd = [self.adb] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""

    def is_connected(self) -> bool:
        """检查是否有设备连接"""
        output = self._run("devices")
        lines = [l for l in output.split("\n") if "\tdevice" in l]
        return len(lines) > 0

    def screenshot(self, output_path: Optional[str] = None) -> str:
        """截取屏幕截图"""
        if output_path is None:
            output_path = os.path.join(SCREENSHOT_DIR, f"screen_{int(time.time())}.png")
        # 在设备上截图
        self._run("shell", "screencap", "-p", "/sdcard/screen.png")
        # 拉取到本地
        self._run("pull", "/sdcard/screen.png", output_path)
        return output_path

    def tap(self, x: int, y: int):
        """点击坐标"""
        self._run("shell", "input", "tap", str(x), str(y))
        time.sleep(0.5)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """滑动"""
        self._run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
        time.sleep(0.5)

    def input_text(self, text: str):
        """输入文字（需要先点击输入框）"""
        # 处理中文：用 ADB broadcast
        escaped = text.replace("'", "\\'")
        self._run("shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", escaped)
        time.sleep(0.3)

    def press_key(self, keycode: str):
        """按键（如 KEYCODE_BACK, KEYCODE_ENTER）"""
        self._run("shell", "input", "keyevent", keycode)
        time.sleep(0.3)

    def press_back(self):
        self.press_key("KEYCODE_BACK")

    def press_enter(self):
        self.press_key("KEYCODE_ENTER")

    def press_home(self):
        self.press_key("KEYCODE_HOME")

    def scroll_down(self):
        """向下滚动一屏"""
        self.swipe(540, 1800, 540, 600, 500)

    def scroll_up(self):
        """向上滚动一屏"""
        self.swipe(540, 600, 540, 1800, 500)

    def open_app(self, package_name: str, activity: str = ""):
        """打开应用"""
        if activity:
            self._run("shell", "am", "start", "-n", f"{package_name}/{activity}")
        else:
            self._run("shell", "monkey", "-p", package_name, "-c",
                      "android.intent.category.LAUNCHER", "1")
        time.sleep(3)

    def get_screen_size(self) -> tuple:
        """获取屏幕分辨率"""
        output = self._run("shell", "wm", "size")
        match = re.search(r'(\d+)x(\d+)', output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 1080, 2400  # 默认值

    def is_app_installed(self, package_name: str) -> bool:
        """检查应用是否已安装"""
        output = self._run("shell", "pm", "list", "packages", package_name)
        return package_name in output

    def install_apk(self, apk_path: str):
        """安装 APK"""
        self._run("install", "-r", apk_path, timeout=60)


# ========== AutoGLM API ==========
class AutoGLMAgent:
    """AutoGLM 视觉Agent"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.history = []

    def analyze_screen(self, screenshot_path: str, instruction: str) -> dict:
        """分析屏幕并获取操作指令"""
        import urllib.request as ur

        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        messages = self.history.copy()
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        })

        payload = json.dumps({
            "model": AUTOGLM_MODEL,
            "messages": messages,
            "max_tokens": 2048
        })

        req = ur.Request(API_URL)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with ur.urlopen(req, payload.encode(), timeout=30) as resp:
                result = json.loads(resp.read())
                assistant_msg = result["choices"][0]["message"]
                # 保留历史
                self.history.append({"role": "user", "content": instruction})
                self.history.append(assistant_msg)
                return result
        except Exception as e:
            print(f"❌ AutoGLM API 错误: {e}", file=sys.stderr)
            return {"error": str(e)}

    def extract_data(self, screenshot_path: str, prompt: str) -> str:
        """从截图中提取结构化数据"""
        import urllib.request as ur

        with open(screenshot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        # 用 GLM-4V 而非 autoglm-phone 做纯数据提取
        payload = json.dumps({
            "model": "glm-4v-plus",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]
            }],
            "max_tokens": 4096
        })

        req = ur.Request(API_URL)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with ur.urlopen(req, payload.encode(), timeout=30) as resp:
                result = json.loads(resp.read())
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ 数据提取错误: {e}", file=sys.stderr)
            return ""

    def reset_history(self):
        self.history = []


# ========== 大众点评抓取流程 ==========
DIANPING_PACKAGE = "com.dianping.v1"

def search_dianping(adb: ADBController, agent: AutoGLMAgent, keyword: str,
                     city: str = "上海", count: int = 10) -> list:
    """搜索大众点评并提取数据"""
    results = []
    print(f"\n🔍 搜索: {city} {keyword}", file=sys.stderr)

    # 1. 打开大众点评
    print("📱 打开大众点评...", file=sys.stderr)
    adb.open_app(DIANPING_PACKAGE)
    time.sleep(3)

    # 2. 截图分析当前状态
    screenshot = adb.screenshot()
    response = agent.analyze_screen(screenshot, f"当前屏幕显示的是什么？请描述。")
    print(f"📸 屏幕状态: {_get_content(response)[:100]}", file=sys.stderr)

    # 3. 点击搜索框
    print("🔍 点击搜索...", file=sys.stderr)
    screenshot = adb.screenshot()
    response = agent.analyze_screen(screenshot,
        "请找到搜索框或搜索按钮的位置，返回其坐标。格式: tap(x, y)")
    action = _get_content(response)
    _execute_action(adb, action)
    time.sleep(1)

    # 4. 输入搜索关键词
    print(f"⌨️ 输入: {keyword}", file=sys.stderr)
    adb.input_text(keyword)
    time.sleep(0.5)
    adb.press_enter()
    time.sleep(3)

    # 5. 循环截图提取数据
    page = 0
    while len(results) < count:
        page += 1
        print(f"\n📄 第 {page} 页 (已收集 {len(results)}/{count})", file=sys.stderr)

        # 截图
        screenshot = adb.screenshot()

        # 用 GLM-4V 提取结构化数据
        extract_prompt = f"""请仔细分析这张大众点评搜索结果截图，提取所有可见的餐厅/商家信息。

请以 JSON 数组格式返回，每个商家包含以下字段（如无该信息则为null）：
- name: 商家名称
- rating: 评分（如 4.5）
- avg_price: 人均消费（如 ¥128）
- cuisine: 菜系/分类
- address: 地址
- review_count: 评论数
- highlights: 推荐菜/特色（数组）

只返回 JSON，不要其他文字。"""

        data_text = agent.extract_data(screenshot, extract_prompt)
        print(f"   提取原文: {data_text[:200]}", file=sys.stderr)

        # 解析 JSON
        try:
            # 尝试从返回文本中提取 JSON 数组
            json_match = re.search(r'\[.*\]', data_text, re.DOTALL)
            if json_match:
                page_results = json.loads(json_match.group())
                # 去重
                for item in page_results:
                    if item.get("name") and item["name"] not in [r["name"] for r in results]:
                        results.append(item)
                        print(f"   ✅ {item['name']} ({item.get('rating', '?')}分, {item.get('avg_price', '?')})", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"   ⚠️ JSON 解析失败", file=sys.stderr)

        if len(results) >= count:
            break

        # 向下滚动
        print("   📜 向下滚动...", file=sys.stderr)
        adb.scroll_down()
        time.sleep(2)

    print(f"\n✅ 共收集 {len(results)} 条数据", file=sys.stderr)
    return results[:count]


def _get_content(response: dict) -> str:
    """从 API 响应中提取文本内容"""
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return str(response.get("error", ""))


def _execute_action(adb: ADBController, action_text: str):
    """解析并执行 AutoGLM 返回的操作指令"""
    # 匹配 tap(x, y)
    tap_match = re.search(r'tap\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', action_text)
    if tap_match:
        x, y = int(tap_match.group(1)), int(tap_match.group(2))
        adb.tap(x, y)
        return

    # 匹配 swipe(x1, y1, x2, y2)
    swipe_match = re.search(r'swipe\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', action_text)
    if swipe_match:
        x1, y1, x2, y2 = [int(swipe_match.group(i)) for i in range(1, 5)]
        adb.swipe(x1, y1, x2, y2)
        return

    # 匹配 type("text")
    type_match = re.search(r'type\s*\(\s*["\'](.+?)["\']\s*\)', action_text)
    if type_match:
        adb.input_text(type_match.group(1))
        return

    print(f"   ⚠️ 无法解析操作: {action_text[:100]}", file=sys.stderr)


# ========== 主程序 ==========
def main():
    parser = argparse.ArgumentParser(description="AutoGLM 大众点评数据抓取")
    parser.add_argument("keyword", help="搜索关键词，如 '外滩餐厅'")
    parser.add_argument("--city", default="上海", help="城市名 (默认: 上海)")
    parser.add_argument("--count", type=int, default=10, help="抓取数量 (默认: 10)")
    parser.add_argument("--output", "-o", help="输出 JSON 文件路径")
    args = parser.parse_args()

    # 检查 API Key
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        print("❌ 请设置 ZAI_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    # 初始化
    adb = ADBController()
    agent = AutoGLMAgent(api_key)

    # 检查设备
    if not adb.is_connected():
        print("❌ 未检测到 Android 设备/模拟器。请先启动模拟器:", file=sys.stderr)
        print("   双击 '启动模拟器.command' 或运行:", file=sys.stderr)
        print(f"   {ANDROID_HOME}/emulator/emulator -avd openclaw_phone &", file=sys.stderr)
        sys.exit(1)

    print("✅ 设备已连接", file=sys.stderr)

    # 检查大众点评是否安装
    if not adb.is_app_installed(DIANPING_PACKAGE):
        print("❌ 大众点评未安装。请先安装 APK:", file=sys.stderr)
        print(f"   {ADB} install dianping.apk", file=sys.stderr)
        sys.exit(1)

    # 搜索并提取
    results = search_dianping(adb, agent, args.keyword, args.city, args.count)

    # 输出
    output = {
        "keyword": args.keyword,
        "city": args.city,
        "count": len(results),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results
    }

    output_json = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n📁 结果已保存到: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
