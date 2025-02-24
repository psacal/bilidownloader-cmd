import os
import logging
import click
import requests
from utils import check_ffmpeg
from models import VideoConfig, DownloadConfig, DownloadTask
from param_help import *

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

SERVER_URL = "http://localhost:5000"

def process_single_download(input_url, video_config, download_config):
    """处理单个下载任务"""
    task = DownloadTask(
        input=input_url,
        video_config=video_config,
        download_config=download_config
    )
    
    try:
        logging.info(f"开始下载: {input_url}")
        
        # 确保 server_url 包含协议前缀
        server_url = download_config.server_url
        if not server_url.startswith(('http://', 'https://')):
            server_url = f"http://{server_url}"
            
        response = requests.post(
            f"{server_url}/download",
            json={
                "input": task.input,
                "video_config": vars(task.video_config),
                "download_config": vars(task.download_config)
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if result["status"] == "success":
            task_id = result["task_id"]
            logging.info(f"任务已添加，任务ID: {task_id}")
            return task_id
        else:
            logging.error(f"下载失败 {input_url}: {result['message']}")
            return None
    except Exception as e:
        logging.error(f"下载异常 {input_url}: {str(e)}")
        return None

def list_tasks(server_url):
    """获取所有任务列表"""
    try:
        if not server_url.startswith(('http://', 'https://')):
            server_url = f"http://{server_url}"

        response = requests.get(f"{server_url}/tasks")
        response.raise_for_status()
        result = response.json()

        if result["status"] == "success":
            tasks = result["tasks"]
            if not tasks:
                print("当前没有任务")
                return

            print("\n当前任务列表:")
            for task in tasks:
                print(f"\n任务ID: {task['task_id']}")
                print(f"输入: {task['input']}")
                print(f"状态: {task['status']}")
                print(f"进度: {task['progress']}%")
                if task['error_message']:
                    print(f"错误信息: {task['error_message']}")
        else:
            logging.error("获取任务列表失败")
    except Exception as e:
        logging.error(f"获取任务列表异常: {str(e)}")

def get_task_status(server_url, task_id):
    """获取单个任务状态"""
    try:
        if not server_url.startswith(('http://', 'https://')):
            server_url = f"http://{server_url}"

        response = requests.get(f"{server_url}/tasks/{task_id}")
        response.raise_for_status()
        result = response.json()

        if result["status"] == "success":
            task = result["task"]
            print(f"\n任务ID: {task['task_id']}")
            print(f"输入: {task['input']}")
            print(f"状态: {task['status']}")
            print(f"进度: {task['progress']}%")
            if task['error_message']:
                print(f"错误信息: {task['error_message']}")
        else:
            logging.error(f"获取任务状态失败: {result.get('message', '未知错误')}")
    except Exception as e:
        logging.error(f"获取任务状态异常: {str(e)}")

def manage_task(server_url, task_id, action):
    """管理任务状态（暂停/恢复/取消）"""
    try:
        if not server_url.startswith(('http://', 'https://')):
            server_url = f"http://{server_url}"

        response = requests.post(f"{server_url}/tasks/{task_id}/{action}")
        response.raise_for_status()
        result = response.json()

        if result["status"] == "success":
            logging.info(result["message"])
        else:
            logging.error(f"操作失败: {result.get('message', '未知错误')}")
    except Exception as e:
        logging.error(f"操作异常: {str(e)}")

@click.group()
def cli():
    """B站视频下载工具"""
    pass

@cli.command()
@click.option('--input',default='',help=inputHelp)
@click.option('--video-quality', default='360P', help=videoQualityHelp)
@click.option('--audio-quality', default='192K', help=audioQualityHelp)
@click.option('--codec',default='H264',help=codecHelp)
@click.option('--download-dir', default='.', help=downloadDirHelp)
@click.option('--cache-dir', default='.', help=cacheDirHelp)
@click.option('--audio-only',default=False,help=audioOnlyHelp)
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
@click.option('--threads',default=4,help=threadsHelp)
def download(input, video_quality, audio_quality, codec, download_dir, cache_dir, audio_only, server_url, threads):   
    """下载视频"""
    check_ffmpeg()
    
    if not input:
        logging.error("请提供下载链接")
        return

    try:
        video_config = VideoConfig(
            video_quality=video_quality,
            audio_quality=audio_quality,
            codec=codec,
            audio_only=audio_only
        )
        
        download_config = DownloadConfig(
            download_dir=download_dir,
            cache_dir=cache_dir,
            server_url=server_url,
            threads=threads
        )

        task_id = process_single_download(input, video_config, download_config)
        if task_id:
            print(f"任务已添加，任务ID: {task_id}")
            print("使用 'python client.py status <task_id>' 查看任务状态")
            
    except Exception as e:
        logging.error(f"程序发生未知异常: {str(e)}")

@cli.command()
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
def list(server_url):
    """列出所有下载任务"""
    list_tasks(server_url)

@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
def status(task_id, server_url):
    """查看指定任务的状态"""
    get_task_status(server_url, task_id)

@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
def pause(task_id, server_url):
    """暂停指定的下载任务"""
    manage_task(server_url, task_id, "pause")

@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
def resume(task_id, server_url):
    """恢复指定的下载任务"""
    manage_task(server_url, task_id, "resume")

@cli.command()
@click.argument('task_id')
@click.option('--server-url', default=SERVER_URL, help=f'服务器地址,默认为{SERVER_URL}')
def cancel(task_id, server_url):
    """取消指定的下载任务"""
    manage_task(server_url, task_id, "cancel")

if __name__ == "__main__":
    cli()