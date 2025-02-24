# bilidownloader-cmd

一个基于Python开发的B站视频下载工具，支持命令行操作，采用客户端-服务器架构设计。

## 功能特性

- 支持B站视频链接、AV号、BV号多种输入方式
- 支持自定义视频质量、音频质量和视频编码
- 支持仅下载音频模式
- 多任务并发下载
- 任务状态管理（暂停/恢复/取消）
- 下载进度实时显示
- 支持自定义下载目录和缓存目录
- 支持多线程下载加速

## 环境要求

- Python 3.6+
- FFmpeg（用于视频混流）

## 安装步骤

1. 克隆项目代码
2. 安装依赖包
3. 确保FFmpeg已安装并添加到系统环境变量

## 使用方法

### 启动服务器

```bash
python server.py [--host HOST] [--port PORT]
```

参数说明：
- `--host`: 服务器监听地址，默认为0.0.0.0
- `--port`: 服务器监听端口，默认为5000

### 客户端命令

1. 下载视频
```bash
python client.py download --input <视频链接/AV号/BV号> [选项]
```

可选参数：
- `--video-quality`: 视频质量（360P/480P/720P/1080P等），默认360P
- `--audio-quality`: 音频质量（64K/132K/192K等），默认192K
- `--codec`: 视频编码（H264/H265/AV1），默认H264
- `--download-dir`: 下载目录，默认为当前目录
- `--cache-dir`: 缓存目录，默认为当前目录
- `--audio-only`: 是否仅下载音频，默认False
- `--server-url`: 服务器地址，默认为http://localhost:5000
- `--threads`: 下载线程数，默认4

2. 查看任务列表
```bash
python client.py list [--server-url SERVER_URL]
```

3. 查看任务状态
```bash
python client.py status <task_id> [--server-url SERVER_URL]
```

4. 暂停任务
```bash
python client.py pause <task_id> [--server-url SERVER_URL]
```

5. 恢复任务
```bash
python client.py resume <task_id> [--server-url SERVER_URL]
```

6. 取消任务
```bash
python client.py cancel <task_id> [--server-url SERVER_URL]
```

## 注意事项

1. 使用前请确保FFmpeg已正确安装
2. 下载前需要先启动服务器
3. 支持的视频质量和编码格式取决于原视频
4. 如果设置的清晰度超过原视频，将自动使用最佳画质下载