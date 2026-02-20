#!/usr/bin/env python3
"""
小红书发布工具 — 通过 Playwright + CDP 在小红书创作平台发布笔记

用法:
  # 发布纯文字笔记（自动生成配图）
  python3 xhs_publish.py --title "标题" --content "正文内容"

  # 发布图文笔记（带图片）
  python3 xhs_publish.py --title "标题" --content "正文内容" --images img1.jpg img2.jpg

  # 带话题和地点
  python3 xhs_publish.py --title "标题" --content "正文内容" --topics "美食" "上海" --location "上海"

  # 仅保存草稿
  python3 xhs_publish.py --title "标题" --content "正文内容" --draft

需要 Chrome Debug 模式运行（已登录小红书）:
  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 &
"""

import argparse
import json
import os
import sys
import time
import urllib.parse

# 环境变量
OPENCLAW_ROOT = os.environ.get("OPENCLAW_HOME", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    import urllib.request
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3)
        data = json.loads(resp.read())
        print(f"🔗 CDP 连接: {data.get('Browser', 'Unknown')}", file=sys.stderr)
        return True
    except Exception:
        return False


def connect_browser(playwright):
    """通过 CDP 连接到已登录的 Chrome"""
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
    contexts = browser.contexts
    if contexts:
        ctx = contexts[0]
        print(f"✅ 已连接（复用已登录会话）", file=sys.stderr)
    else:
        ctx = browser.new_context()
        print(f"⚠️ 新建 context（可能未登录）", file=sys.stderr)
    return browser, ctx


def upload_images(page, image_paths):
    """上传图片到发布页面"""
    if not image_paths:
        return False
    
    # 找到文件上传输入框
    file_input = page.query_selector('input[type="file"]')
    if not file_input:
        # 尝试点击上传区域触发
        upload_area = page.query_selector('.upload-input') or page.query_selector('[class*="upload"]')
        if upload_area:
            upload_area.click()
            time.sleep(1)
            file_input = page.query_selector('input[type="file"]')
    
    if file_input:
        # 获取绝对路径
        abs_paths = [os.path.abspath(p) for p in image_paths]
        file_input.set_input_files(abs_paths)
        print(f"📸 已上传 {len(abs_paths)} 张图片", file=sys.stderr)
        time.sleep(3)  # 等待上传完成
        return True
    else:
        print(f"⚠️ 未找到文件上传输入框", file=sys.stderr)
        return False


def fill_title(page, title):
    """填写标题"""
    # 标题输入框
    title_input = page.query_selector('input.d-text') or page.query_selector('[placeholder*="标题"]')
    if title_input:
        title_input.click()
        title_input.fill(title)
        print(f"📝 标题: {title}", file=sys.stderr)
        return True
    else:
        print(f"⚠️ 未找到标题输入框", file=sys.stderr)
        return False


def fill_content(page, content):
    """填写正文内容"""
    # ProseMirror 富文本编辑器
    editor = page.query_selector('div[role="textbox"].ProseMirror') or page.query_selector('.ProseMirror')
    if editor:
        editor.click()
        # 清空现有内容
        page.keyboard.press("Meta+A")
        page.keyboard.press("Backspace")
        # 输入新内容（支持多行）
        for i, line in enumerate(content.split('\n')):
            if i > 0:
                page.keyboard.press("Enter")
            page.keyboard.type(line, delay=10)
        print(f"✍️ 正文: {content[:50]}...", file=sys.stderr)
        return True
    else:
        print(f"⚠️ 未找到正文编辑器", file=sys.stderr)
        return False


def add_topics(page, topics):
    """添加话题标签"""
    if not topics:
        return
    
    for topic in topics:
        # 点击话题按钮
        topic_btn = page.query_selector('#topicBtn') or page.query_selector('[class*="topic"]')
        if not topic_btn:
            # 尝试通过文本查找
            topic_btn = page.evaluate("""
                () => {
                    const btns = Array.from(document.querySelectorAll('button, div, span'));
                    const btn = btns.find(el => el.textContent.includes('话题'));
                    if (btn) { btn.click(); return true; }
                    return false;
                }
            """)
            if not topic_btn:
                print(f"⚠️ 未找到话题按钮", file=sys.stderr)
                continue
        else:
            topic_btn.click()
        
        time.sleep(1)
        
        # 搜索话题
        search_input = page.query_selector('.topic-search input') or page.query_selector('[placeholder*="话题"]')
        if search_input:
            search_input.fill(topic)
            time.sleep(1)
            # 点击第一个搜索结果
            first_result = page.query_selector('.topic-list-item') or page.query_selector('[class*="topic"] [class*="item"]')
            if first_result:
                first_result.click()
                print(f"#️⃣ 话题: #{topic}", file=sys.stderr)
        
        time.sleep(0.5)


def publish_note(title, content, image_paths=None, topics=None, location=None, draft=False):
    """
    发布小红书笔记的主流程
    
    Args:
        title: 笔记标题
        content: 笔记正文
        image_paths: 图片路径列表（可选）
        topics: 话题标签列表（可选）
        location: 地点（可选）
        draft: 是否仅保存草稿
    
    Returns:
        dict: 发布结果
    """
    _ensure_playwright()
    
    if not _check_cdp_port():
        print("❌ Chrome Debug 端口不可用，请先启动 Chrome Debug 模式", file=sys.stderr)
        print("   运行: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222 &", file=sys.stderr)
        return {"success": False, "error": "Chrome Debug 端口不可用"}
    
    result = {"success": False}
    
    with sync_playwright() as p:
        browser, ctx = connect_browser(p)
        page = ctx.new_page()
        
        try:
            # 1. 打开创作平台发布页
            publish_url = "https://creator.xiaohongshu.com/publish/publish?source=official"
            print(f"🌐 打开发布页面: {publish_url}", file=sys.stderr)
            page.goto(publish_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            
            # 检查是否需要登录
            if "login" in page.url.lower():
                print("❌ 未登录，请先在 Chrome 中登录小红书", file=sys.stderr)
                return {"success": False, "error": "未登录"}
            
            # 2. 切换到"上传图文"标签
            print(f"📄 切换到图文发布模式", file=sys.stderr)
            page.evaluate("""
                () => {
                    const tabs = Array.from(document.querySelectorAll('div, span'));
                    const tab = tabs.find(el => el.textContent === '上传图文');
                    if (tab) tab.click();
                }
            """)
            time.sleep(1)
            
            # 3. 上传图片或使用文字配图
            if image_paths:
                uploaded = upload_images(page, image_paths)
                if not uploaded:
                    print("⚠️ 图片上传失败，尝试使用文字配图", file=sys.stderr)
                    image_paths = None
            
            if not image_paths:
                # 使用"文字配图"功能
                print(f"🎨 使用文字配图生成配图", file=sys.stderr)
                page.evaluate("""
                    () => {
                        const btn = document.querySelector('.text2image-button') 
                            || Array.from(document.querySelectorAll('div, span, button')).find(el => el.textContent.includes('文字配图'));
                        if (btn) btn.click();
                    }
                """)
                time.sleep(1)
                
                # 在文字配图编辑器中输入内容
                text_editor = page.query_selector('.ProseMirror') or page.query_selector('[contenteditable="true"]')
                if text_editor:
                    text_editor.click()
                    # 使用 JavaScript 设置内容
                    preview_text = content[:200] if len(content) > 200 else content
                    # 替换换行符和单引号（避免 f-string 中使用反斜杠）
                    newline = chr(10)
                    html_content = preview_text.replace(newline, "</p><p>").replace("'", "\\'")
                    page.evaluate("""
                        (htmlContent) => {
                            const editor = document.querySelector('.ProseMirror') || document.querySelector('[contenteditable="true"]');
                            if (editor) {
                                editor.innerHTML = '<p>' + htmlContent + '</p>';
                            }
                        }
                    """, html_content)
                
                time.sleep(1)
                
                # 点击"生成图片"
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('span, button, div'));
                        const btn = btns.find(el => el.textContent === '生成图片');
                        if (btn) btn.click();
                    }
                """)
                time.sleep(3)
                
                # 点击"下一步"
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('span, button, div'));
                        const btn = btns.find(el => el.textContent === '下一步');
                        if (btn) btn.click();
                    }
                """)
                time.sleep(2)
            else:
                time.sleep(2)
                # 图片上传后可能需要点击"下一步"
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('span, button, div'));
                        const btn = btns.find(el => el.textContent === '下一步');
                        if (btn) btn.click();
                    }
                """)
                time.sleep(2)
            
            # 4. 填写标题
            fill_title(page, title)
            time.sleep(0.5)
            
            # 5. 填写正文
            fill_content(page, content)
            time.sleep(0.5)
            
            # 6. 添加话题
            if topics:
                add_topics(page, topics)
            
            # 7. 发布或保存草稿
            if draft:
                print(f"💾 保存草稿...", file=sys.stderr)
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const btn = btns.find(el => el.textContent.includes('暂存') || el.textContent.includes('草稿'));
                        if (btn) btn.click();
                    }
                """)
                time.sleep(2)
                result = {"success": True, "action": "draft", "title": title}
                print(f"✅ 草稿已保存: {title}", file=sys.stderr)
            else:
                print(f"🚀 发布笔记...", file=sys.stderr)
                # 勾选用户协议
                page.evaluate("""
                    () => {
                        const checkbox = document.querySelector('[class*="agreement"] input') 
                            || document.querySelector('[type="checkbox"]');
                        if (checkbox && !checkbox.checked) checkbox.click();
                    }
                """)
                time.sleep(0.5)
                
                # 点击发布按钮
                page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const btn = btns.find(el => el.textContent.trim() === '发布' && el.classList.contains('css-k4lz0g'));
                        if (!btn) {
                            const btn2 = btns.find(el => el.textContent.trim() === '发布');
                            if (btn2) btn2.click();
                        } else {
                            btn.click();
                        }
                    }
                """)
                time.sleep(3)
                
                # 检查是否发布成功
                current_url = page.url
                page_text = page.inner_text("body")[:500]
                
                if "publish" not in current_url or "成功" in page_text or "笔记管理" in page_text:
                    result = {"success": True, "action": "publish", "title": title, "url": current_url}
                    print(f"✅ 笔记已发布: {title}", file=sys.stderr)
                else:
                    result = {"success": False, "action": "publish", "title": title, "error": "发布可能未成功，请检查"}
                    print(f"⚠️ 发布状态不确定，请在小红书确认", file=sys.stderr)
        
        except Exception as e:
            print(f"❌ 发布失败: {e}", file=sys.stderr)
            result = {"success": False, "error": str(e)}
        finally:
            page.close()
    
    return result


def main():
    parser = argparse.ArgumentParser(description="小红书笔记发布工具")
    parser.add_argument("--title", required=True, help="笔记标题")
    parser.add_argument("--content", required=True, help="笔记正文内容")
    parser.add_argument("--images", nargs="+", help="图片路径列表")
    parser.add_argument("--topics", nargs="+", help="话题标签列表")
    parser.add_argument("--location", help="地点")
    parser.add_argument("--draft", action="store_true", help="仅保存草稿，不发布")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    
    args = parser.parse_args()
    
    result = publish_note(
        title=args.title,
        content=args.content,
        image_paths=args.images,
        topics=args.topics,
        location=args.location,
        draft=args.draft
    )
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get("success"):
            action = "草稿保存" if result.get("action") == "draft" else "发布"
            print(f"\n✅ {action}成功")
            print(f"   标题: {result.get('title', '')}")
            if result.get("url"):
                print(f"   链接: {result['url']}")
        else:
            print(f"\n❌ 操作失败: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()
