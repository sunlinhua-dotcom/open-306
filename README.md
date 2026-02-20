# OPENCLAW 云端极速部署版

这是为 **Zeabur**（或其他云端服务）准备的极度精简版 OPENCLAW。  
剔除了一切需要本地 macOS/安卓模拟器 以及大尺寸模型的依赖。本地的体积从 3GB+ 瘦身到了几乎 1MB。

## 🚀 包含的技能组

- `skill-router`：技能调度
- `qwen-image`：纯 API 控制的视频/图片生成
- `deep-research`：深度思考搜索
- `excel` / `pptx-creator`：数据/文档处理
- `xiaohongshutools` 与 `web-search`（移除本地特殊环境代码）：通过预装浏览器在云端进行任务

## 🚢 如何在 Zeabur 部署

1. 在本地打开 Terminal，进入这个文件夹：`cd ~/Desktop/OPENCLAW/openclaw-cloud-deployment`
2. 上传到 Github（或者直接使用 Zeabur CLI 发布）：

   ```bash
   git init
   git add .
   git commit -m "Initialize OpenClaw Cloud version"
   # 这里自行 push 到远端仓库，或通过 GitHub Desktop 提交
   ```

3. 在 Zeabur 中选择基于此 GitHub Repo 部署。
4. Zeabur 会自动读取 `Dockerfile`，并监听默认 `8080` 端口。

## 🌍 环境变量注意

在 Zeabur 的环境设置（Variables）中，务必填入对应的 API Keys（不要将其直接写入代码中）：
- `ZAI_API_KEY` (智谱 API)
- `DASHSCOPE_API_KEY` (阿里云通义)
- （如果需要 OpenAI Whisper 代替本地的话配置 `OPENAI_API_KEY`）
