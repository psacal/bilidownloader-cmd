import logging
from typing import Dict, List, Optional
from queue import PriorityQueue
from threading import Lock
from src.common.models import DownloadTask, TaskStatus  # 已经修改为相对导入
from src.common.logger import get_logger
from datetime import datetime

class TaskManager:
    def __init__(self):
        self.logger = get_logger(__name__)
        self._tasks: Dict[str, DownloadTask] = {}
        self._queue = PriorityQueue()
        self._lock = Lock()
        self._running_tasks: Dict[str, DownloadTask] = {}
        self._max_concurrent_downloads = 3  # 默认最大并发下载数

    def set_max_concurrent_downloads(self, max_downloads: int):
        """设置最大并发下载数"""
        with self._lock:
            self._max_concurrent_downloads = max_downloads
            self.logger.info(f"设置最大并发下载数为: {max_downloads}")

    def get_max_concurrent_downloads(self) -> int:
        """获取当前最大并发下载数"""
        return self._max_concurrent_downloads

    def add_task(self, task: DownloadTask) -> str:
        """添加新的下载任务"""
        with self._lock:
            self._tasks[task.task_id] = task
            self._queue.put((-task.priority, task.created_at.timestamp(), task.task_id))
            self.logger.info(f"添加新任务: {task.task_id}")
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
                self.logger.info(f"任务已取消: {task_id}")
                return True
            return False

    def pause_task(self, task_id: str) -> bool:
        """暂停指定的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.PAUSED
                self.logger.info(f"任务已暂停: {task_id}")
                return True
            return False

    def resume_task(self, task_id: str) -> bool:
        """恢复指定的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PAUSED:
                task.status = TaskStatus.PENDING
                self._queue.put((-task.priority, task.created_at.timestamp(), task.task_id))
                self.logger.info(f"任务已恢复: {task_id}")
                return True
            return False

    def get_next_task(self) -> Optional[DownloadTask]:
        """获取下一个要执行的任务"""
        try:
            with self._lock:
                if len(self._running_tasks) >= self._max_concurrent_downloads:
                    self.logger.info("已达到最大并发下载数，无法获取下一个任务。")
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
                task.progress = 100.0 if success else task.progress  # 保留失败任务的进度
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]
                logging.info(f"任务{'完成' if success else '失败'}: {task_id}")

    def validate_task_update(self,task: DownloadTask, **kwargs):
        """
        验证更新任务参数的合理性
        Args:
            task (DownloadTask): 要更新的任务对象
            **kwargs: 任务参数字典
        
        Returns:
            bool: 是否验证通过
        """
        if 'progress' in kwargs:
            progress = kwargs['progress']
            if not (0 <= progress <= 100):
                self.logger.error(f"非法进度值: {progress},必须要在0~100之间")
                return False
            
        if 'status' in kwargs:
            status = kwargs['status']
            self.logger.debug(f"状态值: {status}")
            if status not in TaskStatus.__members__:
                self.logger.error(f"非法状态值: {status}, 必须是TaskStatus的成员")
                return False
        
        return True
            
    def update_task(self, task_id: str,**kwargs) -> bool:
        """
            更新任务进度,状态及其他信息
            Args:
                task_id: 需要更新的任务ID
                **kwargs: 需要更新的参数
            Returns:
                bool: 是否更新成功
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                self.logger.warning(f"任务{task_id}不存在!")
                return False
            
            if not self.validate_task_update(task, **kwargs):
                self.logger.warning(f"任务{task_id}更新失败!,参数:{kwargs}")
                return False

            for key, value in kwargs.items():
                # 目前只完成了进度与状态的更新
                if key == 'progress':
                    task.progress = round(value, 2)
                elif key == 'status':
                    task.status = TaskStatus[value]
            task.last_updated = datetime.now()

            if task_id in self._running_tasks:
                self._running_tasks[task_id] = task
            
            self.logger.debug(f"任务{task_id}更新成功!,参数:{kwargs}")