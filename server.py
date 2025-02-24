import logging
from flask import Flask, request, jsonify
from bilibili_api import video, sync, HEADERS
from utils import *
from download import Downloader
from models import DownloadTask, VideoConfig, DownloadConfig
from task_manager import TaskManager
import click
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
downloader = Downloader()
task_manager = TaskManager()

# 下载工作线程
def download_worker():
    while True:
        task = task_manager.get_next_task()
        if task:
            try:
                download_core(task)
                task_manager.complete_task(task.task_id, True)
            except Exception as e:
                task_manager.complete_task(task.task_id, False, str(e))

# 启动下载工作线程
worker_thread = threading.Thread(target=download_worker, daemon=True)
worker_thread.start()

def select_stream(detecter:video.VideoDownloadURLDataDetecter, video_config: VideoConfig) ->str:
    videoQuality = config2reality(video_config.video_quality)
    audioQuality = config2reality(video_config.audio_quality)
    codec = config2reality(video_config.codec)
    streamsList = detecter.detect()
    streamsListSize = len(streamsList)
    videoIndex=audioIndex=None
    if (detecter.check_flv_stream()):
        logging.info('Flv流,无需选择')
        videoUrl = streamsList[0].url
    else:
        for i in range(streamsListSize):
            if type(streamsList[i]).__name__ == 'VideoStreamDownloadURL':
                if (streamsList[i].video_quality.name == videoQuality) and (streamsList[i].video_codecs.name == codec):
                    videoIndex = i
            elif type(streamsList[i]).__name__ == 'AudioStreamDownloadURL':
                if streamsList[i].audio_quality.name == audioQuality:
                    audioIndex = i
        if (videoIndex != None) and (audioIndex != None):
            videoUrl = streamsList[videoIndex].url
            audioUrl = streamsList[audioIndex].url
        else:
            logging.error("设置的清晰度/编码/音质超过了原视频，自动以最佳画质下载")
            streamsList = detecter.detect_best_streams()
            videoUrl = streamsList[0].url
            audioUrl = streamsList[1].url
    logging.debug(f"视频流链接:{videoUrl}")
    logging.debug(f"音频流链接:{audioUrl}")
    return videoUrl,audioUrl 

def download_core(task: DownloadTask) ->None:
    
    avid, bvid = extract_avid_bvid(task.input)
    bvid = check_input(avid, bvid)
    if bvid is None:
        raise ValueError("未检测到bvid!请检查输入是否正确")
    
    download_video = video.Video(bvid=bvid)
    downloadUrlData = sync(download_video.get_download_url(0))
    Detecter = video.VideoDownloadURLDataDetecter(data=downloadUrlData)
    downloadVideoInfo = sync(download_video.get_info())
    downloadVideoName = downloadVideoInfo["title"]

    fileName = sanitize_filename(downloadVideoName) + '.mp4'
    tempFlv = os.path.join(task.download_config.cache_dir, "flv_temp.flv")
    tempAudio = os.path.join(task.download_config.cache_dir, "audio_temp.m4s")
    tempVideo = os.path.join(task.download_config.cache_dir, "video_temp.m4s")
    output = os.path.join(task.download_config.download_dir, fileName)

    videoUrl, audioUrl = select_stream(Detecter, task.video_config)
    
    if Detecter.check_flv_stream():
        logging.info(f"正在下载视频{downloadVideoName} 的Flv文件")
        downloader.download(videoUrl, tempFlv, task.download_config.threads, True, HEADERS)
        logging.debug('混流开始')
        mix_streams(tempFlv, '', output)
    else:
        if task.video_config.audio_only:
            logging.info("仅下载音频模式")
            logging.info(f"正在下载视频 {downloadVideoName} 的音频流")
            downloader.download(audioUrl, tempAudio, task.download_config.threads, True, HEADERS)
            logging.debug('混流开始')
            mix_streams('', tempAudio, output)
        else:
            logging.info(f"正在下载视频 {downloadVideoName} 的视频流")
            logging.info(f'视频流下载链接:{videoUrl}')
            if not downloader.download(videoUrl, tempVideo):
                raise Exception("视频流下载失败")
            logging.info(f"正在下载视频 {downloadVideoName} 的音频流")
            logging.info(f'音频流下载链接:{audioUrl}')
            if not downloader.download(audioUrl, tempAudio):
                raise Exception("音频流下载失败")
            logging.debug('混流开始')
            mix_streams(tempVideo, tempAudio, output)

@app.route('/download', methods=['POST'])
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
        
        task_id = task_manager.add_task(task)
        return jsonify({"status": "success", "message": "任务已添加", "task_id": task_id})
    except Exception as e:
        logging.error(f"添加任务失败: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/tasks', methods=['GET'])
def list_tasks():
    tasks = task_manager.list_tasks()
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

@app.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = task_manager.get_task(task_id)
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

@app.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    if task_manager.cancel_task(task_id):
        return jsonify({"status": "success", "message": "任务已取消"})
    return jsonify({"status": "error", "message": "无法取消任务"}), 400

@app.route('/tasks/<task_id>/pause', methods=['POST'])
def pause_task(task_id):
    if task_manager.pause_task(task_id):
        return jsonify({"status": "success", "message": "任务已暂停"})
    return jsonify({"status": "error", "message": "无法暂停任务"}), 400

@app.route('/tasks/<task_id>/resume', methods=['POST'])
def resume_task(task_id):
    if task_manager.resume_task(task_id):
        return jsonify({"status": "success", "message": "任务已恢复"})
    return jsonify({"status": "error", "message": "无法恢复任务"}), 400

@click.command()
@click.option('--host', default='0.0.0.0', help='服务器监听地址')
@click.option('--port', default=5000, help='服务器监听端口')
def run_server(host, port):
    """启动下载服务器"""
    logging.info(f"服务器启动于 {host}:{port}")
    app.run(host=host, port=port)

if __name__ == "__main__":
    run_server()