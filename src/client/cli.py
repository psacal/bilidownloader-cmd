import logging
import click
import os
import sys
from rich.console import Console,Group
from rich.table import Table
from rich.progress_bar import ProgressBar
from rich.text import Text
from rich.style import Style
from rich.panel import Panel
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))  # 定位到src目录
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from ..common.param_helps.client_help import *
from ..common.param_helps.shared_help import *
from ..common.utils import check_ffmpeg,extract_bvid,find_project_root
from ..common.models import VideoConfig, DownloadConfig
from ..common.logger import configure_logging,get_logger
from .api import ClientAPI 

console = Console()
PROJECT_ROOT = find_project_root()
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs" / "client"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "client" / "default_config.yaml"
@click.group()
def cli():
    """B站视频下载工具"""
@cli.command()
@click.option('--log-level',default='INFO',type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),help=loglevelHelp)
@click.option('--config', default=None, help=configHelp)
@click.option('--input',default='',help=inputHelp)
@click.option('--video-quality', default=None, help=videoQualityHelp)
@click.option('--audio-quality', default=None, help=audioQualityHelp)
@click.option('--codec',default=None,help=codecHelp)
@click.option('--download-dir', default=None, help=downloadDirHelp)
@click.option('--cache-dir', default=None, help=cacheDirHelp)
@click.option('--log-dir',default=None,help=logDirHelp)
@click.option('--audio-only',default=None,help=audioOnlyHelp)
@click.option('--server-url', default=None, help=f'服务器地址')
@click.option('--threads',default=None,help=threadsHelp)
def download(config, input, video_quality, audio_quality, codec, download_dir, cache_dir, audio_only, server_url, threads, log_level, log_dir):   
    """下载视频"""
    # 初始化基础日志配置
    configure_logging(
        log_path=DEFAULT_LOG_DIR / "bdown.log",
        log_level=log_level,
        rotate_size=10
    )
    logger = get_logger("bdown")
    logger.info(f"目前的日志等级{log_level}") 
    
    check_ffmpeg()

    api = ClientAPI(
        config_path=config or DEFAULT_CONFIG_PATH,
        server_url=server_url,
        threads=threads,
        download_dir=download_dir,
        cache_dir=cache_dir,
        log_dir=log_dir,
        video_quality=video_quality,
        audio_quality=audio_quality,
        codec=codec,
        audio_only=audio_only
    )

    # 使用api.config获取最终配置
    download_config = DownloadConfig(
        download_dir=api.config['download_dir'],
        cache_dir=api.config['cache_dir'],
        threads=api.config['threads'],
        server_url=api.config['server_url']  
    )

    video_config = VideoConfig(
        video_quality=api.config['video_quality'],
        audio_quality=api.config['audio_quality'],
        codec=api.config['codec'],
        audio_only=api.config['audio_only']
    )

    #假如配置文件中有设置日志路径，则保存到指定的路径
    final_log_dir = Path(api.config['log_dir'])
    configure_logging(
        log_path=final_log_dir / "bdown.log",
        log_level=log_level,
        rotate_size=10
    )
    

    download_url_list = []
    if os.path.isfile(input):
        try:
            logger.info(f'批量下载模式！')
            logger.info(f"读取文件:{input}!")
            with open(input, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if line and (not line.startswith('#')):
                        # 排除注释和空行
                        logger.debug(f"已经添加链接{line}到下载列表中")
                        download_url_list.append(line)
        except Exception as e:
            logger.error(f"读取文件失败: {str(e)}")
            return
    else:
        download_url_list.append(input) 

    success_count = 0
    download_url_count = len(download_url_list)
    logging.debug(f"共有{download_url_count}个链接需要下载")
    
    try:
        for link in download_url_list:
            logger.debug(f"从{link}中提取BV号")
            bvid = extract_bvid(link)
            logger.info(f"BV号:{bvid}")
            if bvid == None:
                logger.error("请提供下载链接/下载链接格式不正确")
                logger.info(inputHelp)
                continue
            task_id = api.create_download_task(
                                    input_url=bvid,
                                    video_config=video_config,
                                    download_config=download_config
                                )
            if task_id:
                if download_url_count >= 1:
                    success_count += 1
                    logger.info(f"任务已添加[{success_count}/{download_url_count}]任务ID: {task_id}")
                else:
                    logger.info(f"任务添加失败")
        logger.info("使用 'python client.py status <task_id>' 查看任务状态")
            
    except Exception as e:
        logger.error(f"程序发生未知异常: {str(e)}")

@cli.command()
@click.option('--server-url', default=None, help="指定服务器地址")
def list(server_url):
    """展示任务列表"""
    try:
        api = ClientAPI(server_url=server_url) if server_url else ClientAPI()
        tasks = api.get_task_list()
        
        if not tasks:
            console.print("[yellow]当前没有任务[/yellow]")
            return

        # 创建表格
        table = Table(
            title="B站视频下载任务列表",
            title_style="bold cyan",
            caption_style="dim",
            caption=f"服务器地址: {api.base_url}",
            show_lines=False
        )
        
        # 定义列（保持不变）
        table.add_column("ID", style="cyan", width=12)
        table.add_column("视频标题", style="magenta", width=40)
        table.add_column("状态", width=10)
        table.add_column("进度", justify="right", width=20)
        table.add_column("错误信息", style="red", width=30)

        # 填充数据（修改部分）
        for task in tasks:
            # 安全获取字段值
            task_id = str(task.get('task_id', '未知ID'))
            video_title = str(task.get('input', '未知视频'))[:35]  # 截断长标题
            status = str(task.get('status', 'unknown')).lower()
            progress = task.get('progress', 0) or 0  # 处理None值
            raw_error = task.get('error_message')  # 保留原始值
            error_msg = str(raw_error) if raw_error is not None else None  # 条件转换

            # 状态样式处理
            status_style = {
                "running": Style(color="green", bold=True),
                "paused": Style(color="yellow"),
                "failed": Style(color="red", italic=True)
            }.get(status, Style(color="white"))

            # 进度显示
            progress_display = (
                ProgressBar(
                    total=100,
                    completed=progress,
                    style="blue1",
                    complete_style="bold blue",
                    pulse_style="white"
                ) if status == "running" 
                else Text(f"{progress}%")
            )

            # 错误信息处理
            if error_msg is None:
                error_display = Text("无", style="green")
            else:
                # 先确保error_msg是字符串类型
                error_str = str(error_msg)
                if len(error_str) > 25:
                    error_display = Text(error_str[:22] + "...", style="red")
                else:
                    error_display = Text(error_str, style="red")

            # 添加行
            table.add_row(
                Text(task_id, style="bold"),
                Text(video_title, style=status_style),
                Text(status.upper(), style=status_style),
                progress_display,
                error_display
            )

        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]错误:[/bold red] {str(e)}", style="red")

@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=None, help="指定服务器地址")
def status(task_id, server_url):
    """查看任务详细状态"""
    try:
        api = ClientAPI(server_url=server_url) if server_url else ClientAPI()
        task = api.get_task_status(task_id)
        
        if not task:
            console.print("[red]任务不存在或获取失败[/red]")
            return

        # 状态映射表
        status_map = {
            "running": ("green", "▶ 运行中"),
            "paused": ("yellow", "⏸ 暂停"), 
            "completed": ("cyan", "✓ 完成"),
            "failed": ("red", "✗ 失败")
        }
        color, status_text = status_map.get(
            task['status'].lower(), 
            ("white", "未知状态")
        )

        error_msg = task.get('error_message')
        display_text = "无" if error_msg is None else str(error_msg)

        panel = Panel(
            Group(
                Text(f"任务ID: {task['task_id']}", style=Style(color="cyan", bold=True)),
                Text(f"输入链接: {task['input']}", style=Style(color="magenta")),
                Text(f"状态: {status_text}", style=Style(color=color, bold=True)),
                Text(f"进度: {task['progress']}%", style=Style(color="blue")),
                Text.assemble(
                    ("开始时间: ", "dim"),
                    (task.get('started_at', 'N/A'), "dim cyan")
                ),
                Text.assemble(
                    ("完成时间: ", "dim"),
                    (task.get('completed_at', 'N/A'), "dim cyan")
                ),
                Text(f"错误信息: {display_text}", style="green" if error_msg is None else "red")
            ),
            title="任务详情",
            border_style=color,
            width=80
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[bold red]错误:[/] {str(e)}")

ACTION_NAMES = {
    "pause": "暂停",
    "resume": "恢复",
    "cancel": "取消"
}

def _manage_task(action: str, task_id: str, server_url: str):
    """任务管理通用函数"""
    try:
        api = ClientAPI(server_url=server_url) if server_url else ClientAPI()
        result = getattr(api, f"{action}_task")(task_id)  # 动态调用对应方法
        
        if result:
            console.print(f"[green]✓ 成功{ACTION_NAMES[action]}任务 {task_id}[/]")
        else:
            console.print(f"[yellow]⚠ 操作未生效，可能任务已完成或不存在[/]")
            
    except Exception as e:
        console.print(f"[red]✗ 操作失败: {str(e)}[/]")

# pause命令
@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=None)
def pause(task_id, server_url):
    """暂停指定任务"""
    _manage_task("pause", task_id, server_url)

# resume命令 
@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=None)
def resume(task_id, server_url):
    """恢复指定任务"""
    _manage_task("resume", task_id, server_url)

# cancel命令
@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=None)
def cancel(task_id, server_url):
    """取消指定任务"""
    _manage_task("cancel", task_id, server_url)

if __name__ == "__main__":
    cli()