---
name: qwen-image
description: 生成图片。当用户要求生成图片、创建图片、画图、AI绘图时使用此技能。支持中英文 prompt。
homepage: https://dashscope.aliyuncs.com/
metadata: {"openclaw":{"emoji":"🎨"}}
---

# 通义万相 AI 图片生成

使用阿里云通义万相 API 生成高质量 AI 图片。

## 重要提示

⚠️ **不要使用 DALL-E 或 OpenAI 图片 API！** 本系统没有 OpenAI key。
✅ **必须使用此 skill 的脚本来生成图片。**

## 使用方法

生成图片（返回 URL）：

```bash
DASHSCOPE_API_KEY="sk-4ea5b3f5429e4b6d9851858aefe6898b" python3 {baseDir}/scripts/generate_image.py --prompt "图片描述" --size "1024*1024"
```

生成并保存到本地：

```bash
DASHSCOPE_API_KEY="sk-4ea5b3f5429e4b6d9851858aefe6898b" python3 {baseDir}/scripts/generate_image.py --prompt "图片描述" --size "1024*1024" --filename "/tmp/output.png"
```

## API Key

使用环境变量 `DASHSCOPE_API_KEY`，值为 `sk-4ea5b3f5429e4b6d9851858aefe6898b`

## 可选参数

**尺寸 (--size)：**

- `1664*928` (默认) - 16:9 横版
- `1024*1024` - 正方形
- `720*1280` - 9:16 竖版
- `1280*720` - 16:9 横版（较小）

**模型 (--model)：**

- `qwen-image-max` (默认，最高质量)
- `qwen-image-plus-2026-01-09`
- `qwen-image-turbo`

**其他参数：**

- `--negative-prompt "不要的元素"` - 指定排除内容
- `--no-prompt-extend` - 禁用自动 prompt 增强
- `--watermark` - 添加水印

## 工作流程

1. 使用 `python3` 执行 generate_image.py 脚本（**不要用 uv**）
2. 解析脚本输出，找到以 `MEDIA_URL:` 开头的行
3. 提取该行中的图片 URL
4. 使用 markdown 语法展示图片给用户：`![Generated Image](URL)`
5. 除非用户要求保存，否则不要下载图片

## 注意事项

- 支持中英文 prompt
- 默认返回图片 URL，不下载
- 脚本输出中会包含 `MEDIA_URL:` — 提取这个 URL 并用 markdown 图片语法渲染给用户
- 默认负面提示词已内置，帮助避免常见 AI 图片缺陷
