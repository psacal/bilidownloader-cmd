import asyncio
import threading
import os
from time import time
from bilibili_api import video
from src.common.models import DownloadTask,TaskStatus  
from src.service.download import Downloader  
from src.service.task_manager import TaskManager
from src.common.utils import sanitize_filename, mix_streams  
from src.server.video_service import VideoService  
from src.common.logger import get_logger

class DownloadService:
    def __init__(self, task_manager:TaskManager):
        self.task_manager = task_manager
        self.downloader = Downloader()
        self.video_service = VideoService()
        self.worker_thread = None
        self.logger = get_logger(__name__)
        self.logger.info("DownloadService初始化成功")
    
    def start_worker(self):
        """启动下载工作线程"""
        self.worker_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.worker_thread.start()
        self.logger.info("下载工作线程启动成功")
    
    def _download_worker(self):
        """下载工作线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while True:
            tasks = []
            # 获取多个任务，直到达到最大并发下载数
            while len(tasks) < self.task_manager.get_max_concurrent_downloads():
                task = self.task_manager.get_next_task()
                if task:
                    tasks.append(task)
                else:
                    break
            
            if tasks:
                try:
                    # 使用asyncio.gather并发执行多个任务
                    results = loop.run_until_complete(asyncio.gather(*[self.download_core(task) for task in tasks], return_exceptions=True))
                    for task, result in zip(tasks, results):
                        if isinstance(result, Exception):
                            self.task_manager.complete_task(task.task_id, False, str(result))
                        else:
                            self.task_manager.complete_task(task.task_id, True)
                except Exception as e:
                    for task in tasks:
                        self.task_manager.complete_task(task.task_id, False, str(e))
            else:
                # 如果没有任务，等待一段时间再检查
                loop.run_until_complete(asyncio.sleep(1))

    def _update_progress(self, task: DownloadTask, progress: float):
        """更新任务进度到管理器"""
        if time() - task.last_updated < 0.3:  # 每300ms更新一次
            return
        task.last_updated = time()
        task.progress = round(progress, 2)
        task.status = TaskStatus.DOWNLOADING
        self.task_manager.update_task(task)            
    
    async def download_core(self, task: DownloadTask) -> None:
        """核心下载逻辑"""
        #解析数据
        bvid = task.input
        self.logger.info(f"开始下载: {bvid}")
        self.logger.debug(f"下载配置{task.download_config}")
        self.logger.debug(f"视频配置{task.video_config}")
        
        download_video = video.Video(bvid=bvid)
        downloadUrlData = await download_video.get_download_url(0)
        Detecter = video.VideoDownloadURLDataDetecter(data=downloadUrlData)
        downloadVideoInfo = await download_video.get_info()
        downloadVideoName = downloadVideoInfo["title"]
        self.logger.debug("解析数据成功")
        self.logger.info(f"视频名称:{downloadVideoName}")
        
        #合成临时文件名
        fileName = sanitize_filename(downloadVideoName) + '.mp4'
        tempFlv = os.path.join(task.download_config.cache_dir, f"flv_temp_{task.task_id}.flv")
        tempAudio = os.path.join(task.download_config.cache_dir, f"audio_temp_{task.task_id}.m4s")
        tempVideo = os.path.join(task.download_config.cache_dir, f"video_temp_{task.task_id}.m4s")
        output = os.path.join(task.download_config.download_dir, fileName)
        
        #获取流链接   
        videoUrl, audioUrl = await self.video_service.select_stream(Detecter, task.video_config)
        self.logger.debug('获取流链接成功')
        
        if Detecter.check_flv_mp4_stream():
            self.logger.info(f"正在下载视频{downloadVideoName} 的Flv文件")
            success, error_msg = await self.downloader.download(videoUrl, tempFlv, progress_callback=lambda p: self._update_progress(task, p))
            if not success:
                raise Exception(error_msg)
            self.logger.debug('混流开始')
            await mix_streams(tempFlv, '', output)
        else:
            if task.video_config.audio_only == 'True':
                self.logger.info("仅下载音频模式")
                self.logger.info(f"正在下载视频 {downloadVideoName} 的音频流")
                success, error_msg = await self.downloader.download(audioUrl, tempAudio, progress_callback=lambda p: self._update_progress(task, p))
                if not success:
                    raise Exception(error_msg)
                self.logger.debug('混流开始')
                await mix_streams('', tempAudio, output)
            else:
                self.logger.info(f"正在下载视频 {downloadVideoName} 的视频流")
                success, error_msg = await self.downloader.download(videoUrl, tempVideo, progress_callback=lambda p: self._update_progress(task, p))
                if not success:
                    raise Exception(error_msg)
                self.logger.info(f"正在下载视频 {downloadVideoName} 的音频流")
                success, error_msg = await self.downloader.download(audioUrl, tempAudio, progress_callback=lambda p: self._update_progress(task, p))
                if not success:
                    raise Exception(error_msg)
                self.logger.debug('混流开始')
                await mix_streams(tempVideo, tempAudio, output)