from dataclasses import dataclass

@dataclass
class VideoConfig:
    video_quality: str
    audio_quality: str
    codec: str

@dataclass
class DownloadConfig:
    video_config: VideoConfig
    download_dir: str
    cache_dir: str
    audio_only: bool
    max_workers: int