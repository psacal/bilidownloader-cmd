import os
import threading
from tqdm import tqdm
import requests

class Downloader:
    def __init__(self):
        self.lock = threading.Lock()
        self.chunk_size = 1024 * 1024  # 1MB
        self.default_headers = {'User-Agent': 'Mozilla/5.0'}

    def download(self, url, file_path, num_threads=4, resume=True, headers=None):
        """增强版下载方法
        :param headers: 自定义请求头字典，优先级高于默认头
        """
        try:
            merged_headers = {**self.default_headers, **(headers or {})}
            
            # 获取文件信息
            file_size, accept_ranges = self._get_file_info(url, merged_headers)
            if not accept_ranges:
                num_threads = 1

            # 初始化下载信息
            temp_files = []
            chunks = self._split_chunks(file_size, num_threads)
            
            # 创建进度条
            with tqdm(total=file_size, unit='B', unit_scale=True) as pbar:
                if accept_ranges and num_threads > 1:
                    temp_files = [f"{file_path}.part{i}" for i in range(num_threads)]
                    self._download_chunks(url, chunks, temp_files, pbar, resume, merged_headers)
                    self._merge_files(temp_files, file_path)
                else:
                    self._download_single(url, file_path, pbar, resume, merged_headers)

        except Exception as e:
            print(f"下载失败: {str(e)}")
            raise

    def _get_file_info(self, url, headers):
        """获取文件大小和是否支持断点续传"""
        resp = requests.head(url, headers=headers)
        resp.raise_for_status()
        
        file_size = int(resp.headers.get('Content-Length', 0))
        accept_ranges = resp.headers.get('Accept-Ranges', 'none') == 'bytes'
        return file_size, accept_ranges
    
    def _split_chunks(self, file_size, num_threads):  # 正确的方法定义
        """分割下载区块"""
        chunk_size = file_size // num_threads
        chunks = []
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else file_size - 1
            chunks.append((start, end))
        return chunks

    def _download_chunks(self, url, chunks, temp_files, pbar, resume, headers):
        """多线程下载分块"""
        threads = []
        for i, (start, end) in enumerate(chunks):
            temp_file = temp_files[i]
            downloaded = 0
            
            if resume and os.path.exists(temp_file):
                downloaded = os.path.getsize(temp_file)
                if downloaded >= (end - start + 1):
                    with self.lock:
                        pbar.update(downloaded)
                    continue

            t = threading.Thread(
                target=self._download_range,
                args=(url, start + downloaded, end, temp_file, pbar, resume, headers)
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    def _download_range(self, url, start, end, temp_file, pbar, resume, base_headers):
        """下载指定范围的文件块"""
        # 复制基础headers并设置Range
        headers = base_headers.copy()
        if start < end:
            headers['Range'] = f'bytes={start}-{end}'

        mode = 'ab' if (resume and os.path.exists(temp_file)) else 'wb'
        
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(temp_file, mode) as f:
                for data in r.iter_content(chunk_size=self.chunk_size):
                    f.write(data)
                    with self.lock:
                        pbar.update(len(data))

    def _download_single(self, url, file_path, pbar, resume, base_headers):
        """单线程下载整个文件"""
        headers = base_headers.copy()
        downloaded = 0
        
        if resume and os.path.exists(file_path):
            downloaded = os.path.getsize(file_path)
            headers['Range'] = f'bytes={downloaded}-'
            pbar.update(downloaded)

        mode = 'ab' if resume else 'wb'
        
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(file_path, mode) as f:
                for data in r.iter_content(chunk_size=self.chunk_size):
                    f.write(data)
                    pbar.update(len(data))
                    
    def _merge_files(self, temp_files, file_path):
        """合并临时文件"""
        with open(file_path, 'wb') as f:
            for temp_file in temp_files:
                with open(temp_file, 'rb') as part:
                    f.write(part.read())
                os.remove(temp_file)

# 使用示例（带自定义headers）
if __name__ == "__main__":
    downloader = Downloader()
    custom_headers = {
        'Authorization': 'Bearer your_token',
        'Referer': 'https://example.com'
    }
    downloader.download(
        url="https://example.com/protected_file.zip",
        file_path="protected_file.zip",
        num_threads=8,
        resume=True,
        headers=custom_headers
    )