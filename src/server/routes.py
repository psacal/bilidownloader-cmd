from flask import request, jsonify
from src.common.models import VideoConfig, DownloadConfig, DownloadTask
import logging

class APIRoutes:
    def __init__(self, app, task_manager):
        self.app = app
        self.task_manager = task_manager
        self.register_routes()
    
    def register_routes(self):
        @self.app.route('/download', methods=['POST'])
        def handle_download():
            try:
                data = request.json
                video_config = VideoConfig(**data['video_config'])
                download_config = DownloadConfig(**data['download_config'])
                task = DownloadTask(
                    input=data['input'],
                    video_config=video_config,
                    download_config=download_config
                )
                
                task_id = self.task_manager.add_task(task)
                return jsonify({"status": "success", "message": "任务已添加", "task_id": task_id})
            except Exception as e:
                logging.error(f"添加任务失败: {str(e)}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/tasks', methods=['GET'])
        def list_tasks():
            tasks = self.task_manager.list_tasks()
            return jsonify({
                "status": "success",
                "tasks": [{
                    "task_id": task.task_id,
                    "input": task.input,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message
                } for task in tasks]
            })

        @self.app.route('/tasks/<task_id>', methods=['GET'])
        def get_task(task_id):
            task = self.task_manager.get_task(task_id)
            if not task:
                return jsonify({"status": "error", "message": "任务不存在"}), 404
            
            return jsonify({
                "status": "success",
                "task": {
                    "task_id": task.task_id,
                    "input": task.input,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "error_message": task.error_message
                }
            })

        @self.app.route('/tasks/<task_id>/cancel', methods=['POST'])
        def cancel_task(task_id):
            if self.task_manager.cancel_task(task_id):
                return jsonify({"status": "success", "message": "任务已取消"})
            return jsonify({"status": "error", "message": "无法取消任务"}), 400

        @self.app.route('/tasks/<task_id>/pause', methods=['POST'])
        def pause_task(task_id):
            if self.task_manager.pause_task(task_id):
                return jsonify({"status": "success", "message": "任务已暂停"})
            return jsonify({"status": "error", "message": "无法暂停任务"}), 400

        @self.app.route('/tasks/<task_id>/resume', methods=['POST'])
        def resume_task(task_id):
            if self.task_manager.resume_task(task_id):
                return jsonify({"status": "success", "message": "任务已恢复"})
            return jsonify({"status": "error", "message": "无法恢复任务"}), 400