import os
import json
import logging
import aiohttp
import asyncio
from tqdm import tqdm
from typing import Dict, Optional
from bilibili_api import HEADERS

class Downloader:
    def __init__(self, save_dir: str = "."):
        self.save_dir = save_dir
        self.progress_file = os.path.join(save_dir, ".download_progress.json")
        self._load_progress()

    def _load_progress(self) -> None:
        """加载已保存的下载进度"""
        self.progress: Dict[str, Dict] = {}
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.progress = json.load(f)
            except Exception as e:
                logging.error(f"加载下载进度文件失败: {str(e)}")

    def _save_progress(self) -> None:
        """保存下载进度到文件"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存下载进度文件失败: {str(e)}")

    async def _get_file_size(self, url: str) -> Optional[int]:
        """获取远程文件大小"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, headers=HEADERS) as response:
                    return int(response.headers.get('content-length', 0))
        except Exception as e:
            logging.error(f"获取文件大小失败: {str(e)}")
            return None

    async def download(self, url: str, file_path: str, chunk_size: int = 1024 * 1024) -> tuple[bool, Optional[str]]:
        """异步下载文件，支持断点续传
        
        Args:
            url: 下载链接
            file_path: 保存路径
            chunk_size: 分块大小，默认1MB
            
        Returns:
            tuple[bool, Optional[str]]: (是否成功, 错误信息)
        """
        try:
            # 获取文件信息
            file_size = await self._get_file_size(url)
            if not file_size:
                return False, "获取文件大小失败"

            # 检查是否有未完成的下载
            downloaded_size = 0
            if url in self.progress:
                if os.path.exists(file_path):
                    downloaded_size = os.path.getsize(file_path)
                    if downloaded_size >= file_size:
                        return True, None

            # 设置请求头，支持断点续传
            headers = HEADERS.copy()
            if downloaded_size > 0:
                headers['Range'] = f'bytes={downloaded_size}-'

            # 开始下载
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    mode = 'ab' if downloaded_size > 0 else 'wb'
                    
                    # 更新进度信息
                    self.progress[url] = {
                        'file_path': file_path,
                        'file_size': file_size,
                        'downloaded_size': downloaded_size
                    }
                    self._save_progress()

                    # 使用tqdm显示下载进度
                    with tqdm(total=file_size, initial=downloaded_size,
                             unit='iB', unit_scale=True) as pbar:
                        with open(file_path, mode) as f:
                            async for chunk in response.content.iter_chunked(chunk_size):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    pbar.update(len(chunk))
                                    
                                    # 定期保存进度
                                    self.progress[url]['downloaded_size'] = downloaded_size
                                    self._save_progress()

            # 下载完成后清理进度信息
            if downloaded_size >= file_size:
                if url in self.progress:
                    del self.progress[url]
                    self._save_progress()
                return True, None
            else:
                return False, "下载未完成"

        except Exception as e:
            error_msg = str(e)
            logging.error(f"下载失败: {error_msg}")
            return False, error_msg