inputHelp = """视频链接或视频号，支持以下格式：
- 完整链接：https://www.bilibili.com/video/BV1xx411c7mD
- BV号：BV1xx411c7mD
- av号：av170001
- 纯数字：170001"""

videoQualityHelp = """视频清晰度选择:
- 360P: 流畅
- 480P: 清晰
- 720P: 高清
- 1080P: 全高清
- 1080P_PLUS: 全高清Plus
- 1080P_60: 全高清60帧
- 4K: 超清4K
- HDR: HDR真彩
- DOLBY: 杜比视界
- 8K: 超高清8K"""

audioQualityHelp = """音频质量选择:
- 64K: 流畅
- 132K: 标准
- 192K: 高品质
- HIRES: Hi-Res无损
- DOLBY: 杜比全景声"""

codecHelp = """视频编码器选择:
- H264: AVC编码 (默认)
- H265: HEVC编码
- AV1: AV1编码"""

downloadDirHelp = "下载文件保存目录，默认为项目根目录下的download目录"

cacheDirHelp = "下载临时文件存放目录，默认为项目根目录下的cache目录"

audioOnlyHelp = "是否仅下载音频，默认为False"

maxWorkersHelp = "并发下载线程数，默认为3"

threadsHelp = "下载线程数，默认为4"