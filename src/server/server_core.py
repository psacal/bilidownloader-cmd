import click
import os
import sys
from bilibili_api import select_client
from pathlib import Path

from src.common.param_helps.server_help import *
from src.common.param_helps.shared_help import *
from src.common.logger import configure_logging,get_logger
from src.server.app_factory import ApplicationFactory  
from src.service import config_manager
from src.common.utils import find_project_root

PROJECT_ROOT = find_project_root()
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"/ "server"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "server" / "default_config.yaml"

@click.command()
@click.option('--log-level', default='INFO', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), help=loglevelHelp)
@click.option('--host', default=None, help=hostHelp)
@click.option('--port', default=None, help=portHelp)
@click.option('--config', default=None,help=configHelp)
@click.option('--log-dir',default=None,help=logDirHelp)
def run_server(host, port, config, log_level, log_dir):
    """启动下载服务器"""
    #这里设置的是默认日志目录
    configure_logging(
        log_path=DEFAULT_LOG_DIR / Path("server.log"),
        log_level=log_level,
        rotate_size=10
    )
    logger = get_logger()
    # 设置客户端和日志
    select_client("aiohttp")
    logger.setLevel(log_level)
    logger.info(f"目前的日志等级{log_level}")

    # 创建应用工厂实例并获取应用
    app_factory = ApplicationFactory(config_path=config or DEFAULT_CONFIG_PATH,
                                    log_dir=log_dir,
                                    host=host,
                                    port=port)
    #获取最终配置
    final_config = app_factory.config
    host = app_factory.config['host']
    port = app_factory.config['port']
    final_log_dir = Path(final_config['log_dir'])
    #假如配置文件中有设置日志路径，则保存到指定的路径
    configure_logging(
        log_path=final_log_dir / "server.log",
        log_level=log_level,
        rotate_size=10
    )
    logger.info(f"服务器配置文件加载成功，日志保存在 {final_log_dir}中")

    app = app_factory.create_app()
    app.run(host=host, port=port)
    logger.info(f"服务器启动于 {host}:{port}")

if __name__ == "__main__":
    run_server()