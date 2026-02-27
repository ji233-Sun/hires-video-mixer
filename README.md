# HiRes Video Mixer

将音频转为高品质 FLAC 并替换视频音轨，输出 MKV 格式视频。

## 功能

- 上传任意格式的音频和视频文件
- 音频转换为 FLAC 无损格式（可选质量）
- 视频轨直接复制，不重新编码（无损、速度快）
- 输出 MKV 封装格式

### FLAC 质量选项

| 选项 | 采样率 | 位深 |
|------|--------|------|
| 默认 | 48 kHz | 24 bit |
| 高质量 | 96 kHz | 24 bit |
| 极高质量 | 192 kHz | 24 bit |

## 使用方式

### 直接运行（需要 Python + uv）

```bash
# 安装依赖
uv sync

# 启动（自动打开浏览器）
uv run python app.py
```

启动后访问 http://127.0.0.1:5000

### 使用预构建包

从 [Releases](https://github.com/ji233-Sun/hires-video-mixer/releases) 下载对应平台的包：

- **macOS**: 解压后运行 `./HiResVideoMixer/HiResVideoMixer`
- **Windows**: 解压后运行 `HiResVideoMixer\HiResVideoMixer.exe`（内置 FFmpeg）

## 前置依赖

- **macOS**: 需自行安装 FFmpeg（`brew install ffmpeg`）
- **Windows 预构建包**: FFmpeg 已内置，无需额外安装
- **源码运行**: 需要系统 PATH 中有 FFmpeg

## 技术栈

- Python / Flask
- FFmpeg（音视频处理）
- PyInstaller（打包）
- uv（依赖管理）
