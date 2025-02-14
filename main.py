import os
import logging
import click
from bilibili_api import video,sync
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import *
from download import Downloader
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download.log',encoding='utf-8'),
        logging.StreamHandler()
    ]
)
def select_stream(detecter,video_detail) ->str:
    videoQuality = config2reality(video_detail["video_quality"])
    audioQuality = config2reality(video_detail["audio_quality"])
    codec = config2reality(video_detail["codec"])
    streamsList = detecter.detect()
    streamsListSize = len(streamsList)
    videoIndex=audioIndex=None
    if (detecter.check_flv_stream()):
        print('Flv流,无需选择')
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
    logging.debug("视频流链接:{videoUrl}")
    logging.debug("音频流链接:{audioUrl}")
    return videoUrl,audioUrl 
def download_core(input, video_detail, download_dir, cache_dir, audio_only) ->None:
    downloader = Downloader()
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    avid,bvid = extract_avid_bvid(input)
    bvid = check_input(avid,bvid)
    if (bvid == None):
        logging.error("未检测到bvid!请检查输入是否正确")
        return
    
    download_video = video.Video(bvid=bvid)
    downloadUrlData = sync(download_video.get_download_url(0))
    Detecter = video.VideoDownloadURLDataDetecter(data=downloadUrlData)
    downloadVideoInfo = sync(download_video.get_info())
    downloadVideoName = downloadVideoInfo["title"]
    #mock 如果需要保存其他信息可在此处加入代码

    fileName = sanitize_filename(downloadVideoName) + '.mp4' #最终文件名
    tempFlv = os.path.join(cache_dir,"flv_temp.flv") 
    tempAudio = os.path.join(cache_dir,"audio_temp.m4s")
    tempVideo = os.path.join(cache_dir,"video_temp.m4s")
    output = os.path.join(download_dir,fileName)

    videoUrl,audioUrl = select_stream(Detecter,video_detail)
    if Detecter.check_flv_stream():
        logging.info(f"正在下载视频{downloadVideoName} 的Flv文件")
        download_file(videoUrl,tempFlv)
        logging.debug('混流开始')
        mix_streams(tempFlv,'',output)
    else:
        if audio_only:
            logging.info("仅下载音频模式")
            logging.info(f"正在下载视频 {downloadVideoName} 的音频流")
            downloader.download(audioUrl,tempAudio,4,True,HEADERS)
            logging.debug('混流开始')
            mix_streams('',tempAudio,output)
        else:
            logging.info(f"正在下载视频 {downloadVideoName} 的视频流")
            downloader.download(videoUrl,tempVideo,4,True,HEADERS)
            logging.info(f"正在下载视频 {downloadVideoName} 的音频流")
            downloader.download(audioUrl,tempAudio,4,True,HEADERS)
            logging.debug('混流开始')
            mix_streams(tempVideo,tempAudio,output)

@click.command()
@click.argument('input')
@click.option('--input',default='',help='链接')
@click.option('--video-quality', default='360P', help='画质')
@click.option('--audio-quality', default='192K', help='音质')
@click.option('--codec',default='H264',help='编码')
@click.option('--download-dir', default='.', help='下载目录')
@click.option('--cache-dir', default='.', help='临时目录')
@click.option('--audio-only',default=False,help='仅下载音频开关')
@click.option("-w", "--max-workers", default=3, help="并发下载数")
def main(input,video_quality,audio_quality,codec,download_dir,cache_dir,audio_only,max_workers):   
    check_ffmpeg()
    video_detail = {
                "video_quality":video_quality,
                "audio_quality":audio_quality,
                'codec':codec
            }
    try:
        if os.path.isfile(input):
            logging.info("目前为批量下载模式")
            with open(input) as f:
                urls = [line.strip() for line in f if line.strip()]
                
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(
                    download_core, url, video_detail, download_dir, cache_dir, audio_only
                ) for url in urls]
                for future in as_completed(futures):
                    future.result()
        else: 
            logging.info(f'下载配置:{video_quality},{audio_quality},{codec}')
            download_core(input, video_detail, download_dir, cache_dir, audio_only)
    except Exception as e:
        logging.error(f"程序发生未知异常: {str(e)}")
if __name__ == "__main__":
    main()