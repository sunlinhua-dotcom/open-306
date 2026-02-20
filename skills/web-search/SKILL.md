---
name: web-search
description: "网络搜索 + 大众点评/小红书数据抓取。免费搜索（DuckDuckGo）+ Playwright 浏览器抓取。"
---

# 网络搜索 + 平台数据抓取

## 工具一：网络搜索（web_search.py）

免费搜索，无需 API Key，纯 Python 标准库。

```bash
# 普通搜索
python3 {baseDir}/scripts/web_search.py "搜索关键词"

# 深度搜索（搜索 + 自动抓取前3篇正文）
python3 {baseDir}/scripts/web_search.py "搜索关键词" --deep

# 抓取网页正文
python3 {baseDir}/scripts/web_search.py --fetch "https://example.com"
```

## 工具二：平台数据抓取（browser_fetch.py）⭐

用 Playwright 浏览器直接访问大众点评/小红书等平台。

### 推荐方式：Chrome Debug 模式 🔥

1. **启动 Chrome Debug**: 双击 `启动Chrome调试模式.command`（或手动运行下方命令）
2. **在 Chrome 中登录**目标网站（大众点评/小红书等）
3. **运行抓取**，脚本会自动通过 CDP 连接你的 Chrome

```bash
# macOS 手动启动 Chrome Debug:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Google/Chrome" &

# 搜索大众点评（自动检测 CDP 端口）
OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/browser_fetch.py --search "关键词" --site dianping

# 搜索小红书
OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/browser_fetch.py --search "关键词" --site xiaohongshu

# 抓取具体 URL
OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/browser_fetch.py "https://www.dianping.com/shop/xxx"
```

### 备用方式：Cookie 文件模式

如果不使用 Chrome Debug，需先导出 Cookie：

```bash
# 导出 Cookie（需 Chrome Debug 端口）
OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/cdp_cookie_export.py dianping
OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/cdp_cookie_export.py xiaohongshu

# 然后用独立 headless Chromium 抓取（使用已导出的 Cookie）
TMPDIR=/tmp/pw_profiles PLAYWRIGHT_BROWSERS_PATH={baseDir}/.venv/browsers OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/browser_fetch.py --search "关键词" --site dianping
```

### 支持平台

| --site | 平台 | 需要登录 |
| --- | --- | --- |
| dianping | 大众点评 | ✅ 是 |
| xiaohongshu / xhs | 小红书 | ✅ 是 |
| zhihu | 知乎 | ✅ 是 |
| weibo | 微博 | ✅ 是 |
| bilibili | B站 | 否 |

### 参数

| 参数 | 说明 |
| --- | --- |
| `--search "关键词"` | 站内搜索 |
| `--site dianping` | 指定平台 |
| `--city 上海` | 大众点评城市 |
| `--num 5` | 结果数量 |
| `--json` | JSON 输出 |
| `--mobile` | 模拟手机访问 |

## 工具三：小红书发布（xhs_publish.py）⭐ NEW

通过 Playwright + CDP 在小红书创作平台自动发布笔记。**需要 Chrome Debug 模式且已登录小红书。**

```bash
# 发布纯文字笔记（自动生成配图）
TMPDIR=/tmp/pw_profiles OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/xhs_publish.py --title "标题" --content "正文内容"

# 发布图文笔记（带图片）
TMPDIR=/tmp/pw_profiles OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/xhs_publish.py --title "标题" --content "正文内容" --images /path/to/img1.jpg /path/to/img2.jpg

# 带话题
TMPDIR=/tmp/pw_profiles OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/xhs_publish.py --title "标题" --content "正文内容" --topics "美食" "上海"

# 仅保存草稿（不发布）
TMPDIR=/tmp/pw_profiles OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/xhs_publish.py --title "标题" --content "正文内容" --draft

# JSON 格式输出
TMPDIR=/tmp/pw_profiles OPENCLAW_HOME={baseDir} {baseDir}/.venv/bin/python3 {baseDir}/scripts/xhs_publish.py --title "标题" --content "正文内容" --json
```

### 发布参数

| 参数 | 说明 |
| --- | --- |
| `--title "标题"` | 笔记标题（必填） |
| `--content "正文"` | 笔记正文（必填） |
| `--images img1 img2` | 图片路径列表 |
| `--topics "话题1" "话题2"` | 话题标签 |
| `--location "地点"` | 发布地点 |
| `--draft` | 仅保存草稿 |
| `--json` | JSON 格式输出 |
