import logging
from typing import Dict, List, Optional
from queue import PriorityQueue
from threading import Lock
from src.common.models import DownloadTask, TaskStatus  # 已经修改为相对导入
from datetime import datetime

class TaskManager:
    def __init__(self):
        self._tasks: Dict[str, DownloadTask] = {}
        self._queue = PriorityQueue()
        self._lock = Lock()
        self._running_tasks: Dict[str, DownloadTask] = {}
        self._max_concurrent_downloads = 3  # 默认最大并发下载数

    def set_max_concurrent_downloads(self, max_downloads: int):
        """设置最大并发下载数"""
        with self._lock:
            self._max_concurrent_downloads = max_downloads
            logging.info(f"设置最大并发下载数为: {max_downloads}")

    def get_max_concurrent_downloads(self) -> int:
        """获取当前最大并发下载数"""
        return self._max_concurrent_downloads

    def add_task(self, task: DownloadTask) -> str:
        """添加新的下载任务"""
        with self._lock:
            self._tasks[task.task_id] = task
            self._queue.put((-task.priority, task.created_at.timestamp(), task.task_id))
            logging.info(f"添加新任务: {task.task_id}")
            return task.task_id

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取指定任务的信息"""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[DownloadTask]:
        """获取所有任务的列表"""
        return list(self._tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """取消指定的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status in [TaskStatus.PENDING, TaskStatus.PAUSED]:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                logging.info(f"任务已取消: {task_id}")
                return True
            return False

    def pause_task(self, task_id: str) -> bool:
        """暂停指定的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                logging.info(f"任务已暂停: {task_id}")
                return True
            return False

    def resume_task(self, task_id: str) -> bool:
        """恢复指定的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.PENDING
                self._queue.put((-task.priority, task.created_at.timestamp(), task.task_id))
                logging.info(f"任务已恢复: {task_id}")
                return True
            return False

    def get_next_task(self) -> Optional[DownloadTask]:
        """获取下一个要执行的任务"""
        try:
            with self._lock:
                if len(self._running_tasks) >= self._max_concurrent_downloads:
                    logging.info("已达到最大并发下载数，无法获取下一个任务。")
                    return None
                    
                while not self._queue.empty():
                    _, _, task_id = self._queue.get()
                    task = self._tasks.get(task_id)
                    
                    if task and task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.DOWNLOADING
                        task.started_at = datetime.now()
                        self._running_tasks[task_id] = task
                        return task
                return None
        except Exception as e:
            logging.error(f"获取下一个任务时出错: {str(e)}")
            return None

    def complete_task(self, task_id: str, success: bool, error_message: str = None):
        """标记任务为完成状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                task.completed_at = datetime.now()
                task.error_message = error_message
                task.progress = 100.0
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]
                logging.info(f"任务{'完成' if success else '失败'}: {task_id}")

    def update_task(self, updated_task: DownloadTask) -> bool:
        """更新任务状态（线程安全版）
        
        Args:
            updated_task: 包含最新状态的任务对象
            
        Returns:
            bool: 是否更新成功
        """
        with self._lock:  # 保证线程安全
            # 检查任务是否存在
            existing_task = self._tasks.get(updated_task.task_id)
            if not existing_task:
                logging.warning(f"尝试更新不存在的任务: {updated_task.task_id}")
                return False
            
            # 保留不可变字段（创建时间等）
            updated_task.created_at = existing_task.created_at
            
            # 同步所有可变字段
            self._tasks[updated_task.task_id] = updated_task
            
            # 如果任务正在运行，同步更新运行中任务列表
            if updated_task.task_id in self._running_tasks:
                self._running_tasks[updated_task.task_id] = updated_task
            
            logging.debug(f"任务状态已更新: {updated_task.task_id}")
            return True