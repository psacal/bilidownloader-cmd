from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4
class TaskStatus(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

@dataclass
class VideoConfig:
    video_quality: str #画质
    audio_quality: str #音质
    codec: str #编码
    audio_only: bool = False #仅下载音频模式

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
    error_message: str = None
    progress: float = 0.0
    
    def __post_init__(self):
        if self.task_id is None:
            self.task_id = str(uuid4())
        if self.created_at is None:
            self.created_at = datetime.now()