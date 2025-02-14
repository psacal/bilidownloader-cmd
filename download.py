import os
import json
import time
import hashlib
import threading
from tqdm import tqdm
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class Downloader:
    def __init__(self):
        self.lock = threading.Lock()
        self.chunk_size = 1024 * 1024  # 1MB
        self.default_headers = {'User-Agent': 'Mozilla/5.0'}
        self.temp_prefix = ".dl_temp_"
        self.meta_file = None
        self.session = self._create_retry_session()

    def _create_retry_session(self, retries=5, backoff_factor=0.3):
        """创建带自动重试机制的HTTP会话"""
        session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=(500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def download(self, url, file_path, num_threads=4, resume=True, headers=None):
        """主下载方法"""
        try:
            # 处理路径和目录
            file_dir = os.path.dirname(file_path)
            if file_dir:
                os.makedirs(file_dir, exist_ok=True)
            
            # 合并headers并生成唯一元数据文件名
            merged_headers = {**self.default_headers, **(headers or {})}
            base_name = os.path.basename(file_path)
            self.meta_file = os.path.join(file_dir, f"{self.temp_prefix}{base_name}.meta")

            # 尝试恢复下载
            meta = self._load_metadata()
            if resume and meta and meta["url"] == url:
                print("检测到未完成的下载任务，尝试恢复...")
                return self._resume_download(meta, merged_headers)

            # 获取文件信息
            file_size, accept_ranges, etag = self._get_file_info(url, merged_headers)
            if not accept_ranges:
                num_threads = 1

            # 生成临时文件路径
            temp_files = [
                os.path.join(file_dir, f"{self.temp_prefix}{base_name}.part{i}") 
                for i in range(num_threads)
            ]

            # 明确生成chunks
            chunks = self._split_chunks(file_size, num_threads)

            # 保存元数据
            self._save_metadata({
                "url": url,
                "file_path": file_path,
                "headers": merged_headers,
                "chunks": chunks,  # 使用当前生成的chunks
                "etag": etag,
                "temp_files": temp_files,
                "timestamp": time.time()
            })

            with tqdm(total=file_size, unit='B', unit_scale=True) as pbar:
                if accept_ranges and num_threads > 1:
                    self._download_chunks(url, temp_files, pbar, resume, merged_headers)
                    self._merge_files(temp_files, file_path, chunks)  # 传递当前chunks
                else:
                    self._download_single(url, file_path, pbar, resume, merged_headers)

            self._cleanup()
            self._verify_integrity(url, file_path, merged_headers)

        except Exception as e:
            print(f"\n下载失败: {str(e)}")
            self._cleanup(keep_meta=True)
            raise

    def _resume_download(self, meta, new_headers):
        """恢复下载流程"""
        if "chunks" not in meta:
            raise ValueError("元数据缺少分块信息")
        
        # 验证服务器文件是否变更
        current_size, _, new_etag = self._get_file_info(meta["url"], meta["headers"])
        if meta["etag"] != new_etag or meta["chunks"][-1][1] + 1 != current_size:
            raise ValueError("服务器文件已变更，无法续传")

        # 显示恢复进度
        downloaded = sum(os.path.getsize(f) for f in meta["temp_files"] if os.path.exists(f))
        
        with tqdm(total=current_size, initial=downloaded, unit='B', unit_scale=True) as pbar:
            self._download_chunks(
                meta["url"], 
                meta["temp_files"],
                pbar, 
                resume=True,
                headers=meta["headers"]
            )
            self._merge_files(meta["temp_files"], meta["file_path"], meta["chunks"])
            self._cleanup()
            self._verify_integrity(meta["url"], meta["file_path"], meta["headers"])

    def _get_file_info(self, url, headers):
        """获取文件信息"""
        resp = self.session.head(url, headers=headers)
        resp.raise_for_status()
        return (
            int(resp.headers.get('Content-Length', 0)),
            resp.headers.get('Accept-Ranges', 'none') == 'bytes',
            resp.headers.get('ETag', '')
        )

    def _split_chunks(self, file_size, num_threads):
        """分割下载区块"""
        chunk_size = file_size // num_threads
        return [
            (i * chunk_size, 
             (i + 1) * chunk_size - 1 if i < num_threads - 1 else file_size - 1)
            for i in range(num_threads)
        ]

    def _download_chunks(self, url, temp_files, pbar, resume, headers):
        """多线程下载"""
        chunks = self._split_chunks(pbar.total, len(temp_files))
        threads = []
        for i, (start, end) in enumerate(chunks):
            temp_file = temp_files[i]
            downloaded = os.path.getsize(temp_file) if os.path.exists(temp_file) else 0
            
            if resume and downloaded >= (end - start + 1):
                with self.lock:
                    pbar.update(downloaded)
                continue

            t = threading.Thread(
                target=self._download_range,
                args=(url, start + downloaded, end, temp_file, pbar, headers)
            )
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()

    def _download_range(self, url, start, end, temp_file, pbar, headers):
        """范围下载"""
        # 确保临时文件目录存在
        temp_dir = os.path.dirname(temp_file)
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
        
        # 复制headers并设置Range
        req_headers = headers.copy()
        if start < end:
            req_headers['Range'] = f'bytes={start}-{end}'

        mode = 'ab' if os.path.exists(temp_file) else 'wb'
        
        try:
            with self.session.get(url, headers=req_headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(temp_file, mode) as f:
                    for data in r.iter_content(chunk_size=self.chunk_size):
                        f.write(data)
                        with self.lock:
                            pbar.update(len(data))
        except Exception as e:
            self._save_metadata()  # 异常时保存进度
            raise

    def _download_single(self, url, file_path, pbar, resume, headers):
        """单线程下载"""
        req_headers = headers.copy()
        downloaded = 0
        
        if resume and os.path.exists(file_path):
            downloaded = os.path.getsize(file_path)
            req_headers['Range'] = f'bytes={downloaded}-'
            pbar.update(downloaded)

        mode = 'ab' if resume else 'wb'
        
        with self.session.get(url, headers=req_headers, stream=True) as r:
            r.raise_for_status()
            with open(file_path, mode) as f:
                for data in r.iter_content(chunk_size=self.chunk_size):
                    f.write(data)
                    pbar.update(len(data))

    def _merge_files(self, temp_files, file_path, chunks):
        """合并临时文件"""
        if chunks is None:
            raise ValueError("分块信息缺失，无法验证临时文件完整性")
        
        if len(temp_files) != len(chunks):
            raise ValueError(f"临时文件数量({len(temp_files)})与分块数({len(chunks)})不匹配")

        # 验证临时文件完整性
        for i, temp_file in enumerate(temp_files):
            if not os.path.exists(temp_file):
                raise FileNotFoundError(f"临时文件缺失: {temp_file}")
            
            actual_size = os.path.getsize(temp_file)
            start, end = chunks[i]
            expected_size = end - start + 1
            
            if actual_size != expected_size:
                raise ValueError(f"临时文件损坏: {temp_file} 预期大小{expected_size}, 实际{actual_size}")

        # 执行合并
        with open(file_path, 'wb') as f:
            for temp_file in temp_files:
                with open(temp_file, 'rb') as part:
                    f.write(part.read())
                os.remove(temp_file)

    def _verify_integrity(self, url, file_path, headers):
        """增强版完整性校验"""
        # 获取服务器最新信息
        actual_size = os.path.getsize(file_path)
        expected_size, _, etag = self._get_file_info(url, headers)
        
        # 大小校验
        if actual_size != expected_size:
            os.remove(file_path)
            raise ValueError(f"文件大小不匹配: 预期{expected_size}字节, 实际{actual_size}字节")

        print(f"完整性校验通过，文件大小: {actual_size/1024/1024:.2f}MB")

    def _calculate_file_hash(self, file_path, algorithm='md5', block_size=4096):
        """计算本地文件哈希值"""
        hasher = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _save_metadata(self, data=None):
        """保存元数据"""
        if data:
            # 确保保存完整的chunks信息
            data["chunks"] = [tuple(c) for c in data["chunks"]]  # 转换为可序列化格式
            with open(self.meta_file, 'w') as f:
                json.dump(data, f, indent=2)

    def _load_metadata(self):
        """加载元数据"""
        if os.path.exists(self.meta_file):
            with open(self.meta_file, 'r') as f:
                return json.load(f)
        return None

    def _cleanup(self, keep_meta=False):
        """清理临时文件"""
        if self.meta_file and os.path.exists(self.meta_file) and not keep_meta:
            os.remove(self.meta_file)

# 使用示例
if __name__ == "__main__":
    downloader = Downloader()
    try:
        downloader.download(
            url="https://example.com/video.mp4",
            file_path="./videos/video.mp4",
            num_threads=4,
            resume=True,
            headers={
                'Authorization': 'Bearer xyz123',
                'Custom-Header': 'value'
            }
        )
    except KeyboardInterrupt:
        print("\n下载已中断，下次运行将自动恢复")