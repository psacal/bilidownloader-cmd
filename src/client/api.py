import os
import requests
import logging
from pathlib import Path
from typing import Optional,List,Dict,Any

from ..common.models import VideoConfig, DownloadConfig 
from ..common.param_helps.client_help import inputHelp
from ..common.logger import get_logger
from ..service.config_manager import UnifiedConfigManager 

class ClientAPI:
    def __init__(self,config_path: str = None,**overrides):
        self.logger = get_logger("ClientApi")
        """
        初始化客户端API
        """
        """ 
        :param overrides: 可覆盖配置项，支持：
            - server_url: 服务器地址 (str)
            - threads: 线程数 (int)
            - download_dir: 下载目录 (str/Path)
            - cache_dir: 缓存目录 (str/Path)
            - video_quality: 视频质量 (int)
            - audio_quality: 音频质量 (int)
            - codec: 编解码器 (str)
            - audio_only: 仅音频模式 (bool)
        """
        _template = {
            "server_url": "http://127.0.0.1:5000",
            "audio_only": "false",
            "audio_quality": "192K",
            "codec": "H264",
            "threads": "4",
            "video_quality": "360P",
            'log_level': 'INFO',
            'cache_dir': "cache",   
            'download_dir': "download",
            'config_dir': str(Path('configs') / 'client'),
            'log_dir': str(Path('logs') / 'client')
        }
        self.config_manager = UnifiedConfigManager(_template,config_path)
        self.logger.info(f"配置文件路径：{self.config_manager.config_path}")
        self.config = self.config_manager.apply_overrides(overrides)
        #print(self.config)
        self.base_url = self.config['server_url']

    def create_download_task(
        self,
        input_url: str,
        video_config: VideoConfig,
        download_config: DownloadConfig
    ) -> Optional[str]:
        """
        创建下载任务
        返回: 任务ID或None
        """
        try:
            self.logger.info(f"开始下载: {input_url}")
            
            server_url = self.base_url
            
            response = requests.post(
                f"{server_url}/download",
                json={
                    "input": input_url,
                    "video_config": vars(video_config),
                    "download_config": vars(download_config)
                }
            )
            response.raise_for_status()
            
            result = response.json()
            if result["status"] == "success":
                return result["task_id"]
            else:
                self.logger.error(f"下载失败: {result.get('message')}")
                return None
                
        except Exception as e:
            self.logger.error(f"下载异常: {str(e)}")
            return None

    def get_task_list(self) -> List[Dict]:
        """
        获取任务列表(原list_tasks)
        返回: 任务字典列表
        """
        try:
            response = requests.get(f"{self.base_url}/tasks")
            response.raise_for_status()
            result = response.json()

            if result["status"] == "success":
                return result.get("tasks", [])
            else:
                self.logger.error("获取任务列表失败")
                return []
                
        except Exception as e:
            self.logger.error(f"获取任务列表异常: {str(e)}")
            return []
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取单个任务状态"""
        try:
            response = requests.get(f"{self.base_url}/tasks/{task_id}")
            response.raise_for_status()
            return response.json().get("task")
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {str(e)}")
            return None
        
    def manage_task(self, task_id: str, action: str) -> bool:
        """通用任务管理方法"""
        try:
            response = requests.post(
                f"{self.base_url}/tasks/{task_id}/{action}"
            )
            return response.json().get("status") == "success"
        except Exception as e:
            self.logger.error(f"操作{action}失败: {str(e)}")
            return False
    def pause_task(self, task_id: str) -> bool:
        return self.manage_task(task_id, "pause")

    def resume_task(self, task_id: str) -> bool:
        return self.manage_task(task_id, "resume")

    def cancel_task(self, task_id: str) -> bool:
        return self.manage_task(task_id, "cancel")
    
    @staticmethod
    def _parse_log_level(level_str: str) -> int:
        level_map = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        return level_map.get(level_str.lower(), logging.INFO)