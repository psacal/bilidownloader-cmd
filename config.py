import os
import yaml
import logging
from typing import Dict, Any

DEFAULT_CONFIG = {
    'server': {
        'host': '0.0.0.0',
        'port': 5000
    },
    'client': {
        'server_url': 'http://localhost:5000',
        'video_quality': '360P',
        'audio_quality': '192K',
        'codec': 'H264',
        'download_dir': '.',
        'cache_dir': '.',
        'audio_only': False,
        'threads': 4
    }
}

def load_config(config_file: str = 'config.yaml') -> Dict[str, Any]:
    """加载配置文件，如果文件不存在则创建默认配置"""
    if not os.path.exists(config_file):
        create_default_config(config_file)
        return DEFAULT_CONFIG

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f)
            if not user_config:
                return DEFAULT_CONFIG
            
            # 合并配置，确保所有必要的字段都存在
            merged_config = DEFAULT_CONFIG.copy()
            if 'server' in user_config:
                merged_config['server'].update(user_config['server'])
            if 'client' in user_config:
                merged_config['client'].update(user_config['client'])
                
            return merged_config
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        return DEFAULT_CONFIG

def create_default_config(config_file: str):
    """创建默认配置文件"""
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, default_flow_style=False)
        logging.info(f"已创建默认配置文件: {config_file}")
    except Exception as e:
        logging.error(f"创建配置文件失败: {str(e)}")

def get_server_config(config_file: str = 'config.yaml') -> Dict[str, Any]:
    """获取服务器配置"""
    return load_config(config_file)['server']

def get_client_config(config_file: str = 'config.yaml') -> Dict[str, Any]:
    """获取客户端配置"""
    return load_config(config_file)['client']