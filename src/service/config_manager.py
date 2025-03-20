from copy import deepcopy
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from src.common.logger import get_logger
from src.common.utils import find_project_root

class UnifiedConfigManager:
    """统一配置管理器（简化版）"""
    
    def __init__(self, config_template: Dict, config_path: Optional[str] = None):
        # 基础配置
        self._USER_TEMPLATE = config_template
        self.logger = get_logger(__name__)
        self.project_root = find_project_root()
        
        # 初始化配置路径
        self.logger.info(f"传入的配置文件路径: {config_path}")
        self.config_path = self._init_config_path(config_path)
        self.logger.info(f"配置文件路径: {self.config_path}")
        
        # 加载配置
        self.config = self._load_or_create_config()
        self._ensure_paths()

    def apply_overrides(self, overrides: Dict[str, Any]) -> Dict:
        """应用配置覆盖"""
        merged = deepcopy(self.config)
        for k, v in overrides.items():
            if v is not None:
                merged[k] = self._process_value(k, v)
        self.config = self._postprocess(merged)
        return self.config

    def _init_config_path(self, config_path: Optional[str]) -> Path:
        """
        初始化配置文件路径，确保配置文件所在目录存在。
        如果用户未指定配置文件路径或指定的路径不存在，则使用默认路径。
        """
        if config_path:
            path = Path(config_path).expanduser().resolve()
            try:
                path.relative_to(self.project_root)
            except ValueError:
                raise ValueError(f"配置文件必须在项目目录内: {path}")
            
            # 检查文件是否存在
            if path.exists():
                self.logger.info(f"用户指定的配置文件路径: {path}")
                return path
            else:
                self.logger.warning(f"用户指定的配置文件路径不存在: {path}")
        
        # 使用默认路径
        self.logger.info(f"未找到配置文件,将创建默认文件: {self.project_root}")
        default_dir = Path(self._USER_TEMPLATE.get('config_dir'))
        default_path = self.project_root / default_dir / "default_config.yaml"
        self.logger.debug(f"创建默认文件: {default_path}")
        default_path.parent.mkdir(exist_ok=True, parents=True)
        return default_path

    def _load_or_create_config(self) -> Dict:
        """加载或创建配置"""
        if not self.config_path.exists():
            self._create_config_file()
            self.logger.info(f"创建默认配置文件: {self.config_path}成功")
            return deepcopy(self._USER_TEMPLATE)
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f) or {}
                self.logger.info(f"加载配置文件: {self.config_path}成功")
                return self._merge_configs(file_config)
        except Exception as e:
            self.logger.error(f"配置加载失败: {str(e)}")
            return deepcopy(self._USER_TEMPLATE)

    def _merge_configs(self, file_config: Dict) -> Dict:
        """合并用户模板与文件配置"""
        merged = deepcopy(self._USER_TEMPLATE)
        for k, v in file_config.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v
        self.logger.debug(f"合并完的配置: {merged}")
        return merged

    def _process_value(self, key: str, value: Any) -> Any:
        """路径处理"""
        if 'dir' in key or 'path' in key:
            path = Path(str(value))
            return str(path if path.is_absolute() else self.project_root / path)
        return value

    def _ensure_paths(self) -> None:
        """创建所有目录项"""
        for key, value in self.config.items():
            if ('dir' in key or 'path' in key) and value:
                path = Path(value)
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                    self.logger.debug(f"创建目录: {path}")

    def _postprocess(self, config: Dict) -> Dict:
        """配置后处理"""
        # 类型转换
        if 'port' in config:
            try:
                config['port'] = int(config['port'])
            except (ValueError, TypeError):
                config['port'] = 5000

        if 'server_url' in config:
            if not config['server_url'].startswith(('http://', 'https://')):
                config['server_url'] = f"http://{config['server_url']}"
        
        # 日志级别验证
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if 'log_level' in config and config['log_level'].upper() not in valid_levels:
            config['log_level'] = 'INFO'
        
        return config

    def _create_config_file(self) -> None:
        """
        创建新配置文件并写入默认模板。
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self._USER_TEMPLATE, f, allow_unicode=True)
            self.logger.info(f"默认配置文件已写入: {self.config_path}")
        except Exception as e:
            self.logger.error(f"创建默认配置文件失败: {str(e)}")
            raise