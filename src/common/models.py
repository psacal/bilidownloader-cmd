from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

class TaskStatus(Enum):
    PENDING = "等待中"       # 初始状态
    PARSING = "解析中"      # 解析视频信息阶段
    DOWNLOADING = "下载中"
    DOWNLOADING_VIDEO = "视频下载中" #下载视频流
    DOWNLOADING_AUDIO = "音频下载中" #下载音频流
    MERGING = "混流中"      # 混流操作阶段
    CLEANING = "清理中"     # 临时文件清理阶段
    COMPLETED = "已完成"    
    FAILED = "失败"        
    PAUSED = "已暂停"

    def __str__(self):
        return self.value  # 返回可读的字符串表示
@dataclass
class VideoConfig:
    video_quality: str #画质
    audio_quality: str #音质
    codec: str #编码
    audio_only: bool = False

@dataclass
class DownloadConfig:
    download_dir: str
    cache_dir: str
    server_url: str
    threads: int = 4

@dataclass
class DownloadTask:
    input: str
    video_config: VideoConfig
    download_config: DownloadConfig
    task_id: str = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    error_message: Optional[str] = None
    progress: float = 0.0
    last_updated :datetime = 0.0
    def __post_init__(self):
        if self.task_id is None:
            self.task_id = str(uuid4())
        if self.created_at is None:
            self.created_at = datetime.now()