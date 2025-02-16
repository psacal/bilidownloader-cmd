import os
import json
import time
import glob
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
        self.temp_prefix = ".dl_"
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
            # 生成唯一任务ID
            task_id = hashlib.md5(f"{url}_{os.path.abspath(file_path)}".encode()).hexdigest()[:8]
            base_name = os.path.basename(file_path)
            unique_prefix = f"{self.temp_prefix}{task_id}_{base_name}"
            file_dir = os.path.dirname(file_path)
            
            # 创建目标目录
            if file_dir:
                os.makedirs(file_dir, exist_ok=True)
            
            # 初始化文件路径
            self.meta_file = os.path.join(file_dir, f"{unique_prefix}.meta")
            temp_files = [os.path.join(file_dir, f"{unique_prefix}.part{i}") for i in range(num_threads)]

            # 尝试恢复下载
            meta = self._load_metadata()
            if resume and meta and meta.get("unique_prefix") == unique_prefix:
                print(f"恢复任务 [{task_id}]...")
                return self._resume_download(meta, headers or {})

            # 获取文件信息
            merged_headers = {**self.default_headers, **(headers or {})}
            file_size, accept_ranges, etag = self._get_file_info(url, merged_headers)
            if not accept_ranges:
                num_threads = 1

            # 生成分块信息
            chunks = self._split_chunks(file_size, num_threads)

            # 保存元数据
            self._save_metadata({
                "unique_prefix": unique_prefix,
                "url": url,
                "file_path": os.path.abspath(file_path),
                "headers": merged_headers,
                "chunks": chunks,
                "etag": etag,
                "temp_files": temp_files,
                "timestamp": time.time()
            })

            # 开始下载
            with tqdm(total=file_size, unit='B', unit_scale=True, desc=base_name) as pbar:
                if accept_ranges and num_threads > 1:
                    self._download_chunks(url, temp_files, pbar, resume, merged_headers)
                    self._merge_files(temp_files, file_path, chunks)
                else:
                    self._download_single(url, file_path, pbar, resume, merged_headers)

            # 清理并验证
            self._cleanup()
            self._verify_integrity(url, file_path, merged_headers)

        except Exception as e:
            print(f"\n下载失败: {str(e)}")
            self._cleanup(keep_meta=True)
            raise

    def _resume_download(self, meta, new_headers):
        """恢复下载流程"""
        # 验证元数据完整性
        required_keys = ["unique_prefix", "url", "file_path", "chunks", "etag", "temp_files"]
        if any(key not in meta for key in required_keys):
            raise ValueError("元数据损坏，无法恢复下载")

        # 验证服务器文件是否变更
        current_size, _, new_etag = self._get_file_info(meta["url"], meta["headers"])
        if meta["etag"] != new_etag or meta["chunks"][-1][1] + 1 != current_size:
            raise ValueError("服务器文件已变更，无法续传")

        # 显示恢复进度
        downloaded = sum(os.path.getsize(f) for f in meta["temp_files"] if os.path.exists(f))
        
        with tqdm(total=current_size, initial=downloaded, unit='B', unit_scale=True, desc=os.path.basename(meta["file_path"])) as pbar:
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
        """获取文件元信息"""
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
        # 确保目录存在
        temp_dir = os.path.dirname(temp_file)
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
        
        # 设置请求头
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
            print(f"发生以下错误 {e}")
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
        # 防御性校验
        if not chunks or len(temp_files) != len(chunks):
            raise ValueError("无效的分块信息")
        
        # 验证临时文件
        for i, temp_file in enumerate(temp_files):
            if not os.path.exists(temp_file):
                raise FileNotFoundError(f"临时文件缺失: {temp_file}")
            
            actual_size = os.path.getsize(temp_file)
            expected_size = chunks[i][1] - chunks[i][0] + 1
            if actual_size != expected_size:
                raise ValueError(f"文件分块损坏: {temp_file} (预期 {expected_size}B, 实际 {actual_size}B)")

        # 执行合并
        with open(file_path, 'wb') as f:
            for temp_file in temp_files:
                with open(temp_file, 'rb') as part:
                    f.write(part.read())
                os.remove(temp_file)

    def _verify_integrity(self, url, file_path, headers):
        """完整性校验"""
        # 获取服务器信息
        server_size, _, etag = self._get_file_info(url, headers)
        local_size = os.path.getsize(file_path)
        
        # 大小校验
        if local_size != server_size:
            os.remove(file_path)
            raise ValueError(f"文件大小不匹配 (服务器: {server_size}B, 本地: {local_size}B)")

        print(f"验证通过: {local_size/1024/1024:.2f} MB")

    def _calculate_hash(self, file_path, algorithm='md5', block_size=4096):
        """计算文件哈希值"""
        hasher = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _save_metadata(self, data=None):
        """保存元数据"""
        if data and self.meta_file:
            data["chunks"] = [list(c) for c in data["chunks"]]  # 转换为可序列化格式
            with open(self.meta_file, 'w') as f:
                json.dump(data, f, indent=2)

    def _load_metadata(self):
        """加载元数据"""
        if self.meta_file and os.path.exists(self.meta_file):
            try:
                with open(self.meta_file, 'r') as f:
                    data = json.load(f)
                data["chunks"] = [tuple(c) for c in data["chunks"]]  # 转换回元组
                return data
            except:
                pass
        return None

    def _cleanup(self, keep_meta=False):
        """清理临时文件"""
        if self.meta_file and os.path.exists(self.meta_file):
            try:
                # 读取元数据获取唯一前缀
                with open(self.meta_file, 'r') as f:
                    meta = json.load(f)
                prefix = meta["unique_prefix"]
                dir_path = os.path.dirname(self.meta_file)
                
                # 删除所有相关文件
                for f in glob.glob(os.path.join(dir_path, f"{prefix}*")):
                    os.remove(f)
            except Exception as e:
                print(f"清理失败: {str(e)}")

if __name__ == "__main__":
    d=Downloader()
    d.download("https://i-582.wwentua.com:446/01251900219514865bb/2025/01/22/31fc737bff768597a71a9842fa27f036.zip?st=PbLKmfrrLkLRY4s8D2BPVA&e=1737806766&b=AQFZFVQXVCNQZFBgCy9UDwEQDCJUMARlADwAf1UzAiAGIgo7AixTZlgjVzQKvAazAt5Z4FbbAZEGs1zKU_bsF4QHeWftUslTHUIJQ4gvgVOYBegwqVDwEcg_c_c&fi=219514865&pid=119-2-194-240&up=2&mp=0&co=0",
               "b.zip")