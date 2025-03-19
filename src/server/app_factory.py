from flask import Flask
from pathlib import Path
from src.service.task_manager import TaskManager
from src.service.config_manager import UnifiedConfigManager 
from src.server.download_service import DownloadService  
from src.server.routes import APIRoutes  
from src.common.logger import get_logger

class ApplicationFactory:
    """应用工厂类，封装Flask应用创建逻辑"""
    
    def __init__(self,config_path: str = None,**overrides):
        _template ={
            'host': '0.0.0.0',
            'port': 5000,
            'log_level': 'INFO',
            'log_dir': str(Path('logs') / 'server'),
            'cache_dir': "cache",   
            'download_dir': "download",
            'config_dir': str(Path('configs') / 'server')
        }
        self.logger = get_logger(__name__)
        self.app = Flask(__name__)
        self.config_manager = UnifiedConfigManager(_template,config_path)
        self.config = self.config_manager.apply_overrides(overrides)
        self.task_manager = TaskManager()
        self._initialize_services()
        self._register_routes()
    
    def _initialize_services(self):
        """初始化核心服务"""
        self.download_service = DownloadService(self.task_manager)
        self.download_service.start_worker()
        self.logger.info("初始化核心服务成功")
    
    def _register_routes(self):
        """注册API路由"""
        APIRoutes(self.app, self.task_manager)
        self.logger.info("注册API路由成功")
    
    def create_app(self):
        """获取配置完成的Flask应用"""
        self.logger.info("创建Flask应用成功")
        return self.app