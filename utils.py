import re
import os
import logging
import requests
from tqdm import tqdm
import ffmpeg
import subprocess
import bilibili_api
from bilibili_api import HEADERS
def check_input(avid,bvid) ->str:
    if avid and bvid:
        # 如果同时存在AV号和BV号，则报错
        logging.error("请勿同时输入AV号与BV号")
    elif avid:
        # 为AV号则转为BV号 注意此处aid2bvid传入int返回str
        bvid = bilibili_api.aid2bvid(int(avid))
        return bvid
    elif bvid:
        # 如果不存在AV号但存在BV号，则直接返回BV号
        return bvid
    else:
        # 如果都不存在，则返回无效输入提示
        logging.error("什么也没有呢")
        return None
def extract_avid_bvid(url_or_code:str) -> str:
    '''
        从输入中分离avid,bvid
    '''
    avid_pattern = re.compile(r'[aA][vV](\d+)')
    bvid_pattern = re.compile(r'[bB][vV][\d\w]+')
    number_pattern = re.compile(r'^\d+$')
    avid_match = avid_pattern.search(url_or_code)
    bvid_match = bvid_pattern.search(url_or_code)
    number_match = number_pattern.search(url_or_code)
    avid = avid_match.group(1) if avid_match else None
    bvid = bvid_match.group(0) if bvid_match else None
    number = number_match.group(0) if number_match else None
    if avid == None and bvid == None:
        if number_match :
            avid = number
    if bvid != None:
        if bvid.startswith(('Bv', 'bV', 'bv')):
        # 将前缀统一改为 BV，并连接上后面的字符串
            return 'BV' + bvid[2:]
        else:
            # 如果输入不符合条件，直接返回原字符串
            return avid,bvid
    return avid, bvid
def config2reality(str) -> str :
    qualityOfVideoAndAudio = {
        #视频清晰度
        '360P': '_360P',
        '480P': '_480P',
        '720P': '_720P',
        '1080P': '_1080P',
        '1080P_PLUS': '_1080P_PLUS',
        '1080P_60': '_1080P_60',
        '4K': '_4K',
        'HDR': 'HDR',
        'DOLBY': 'DOLBY',
        '8K': '_8K',
        #音频清晰度
        '64K': '_64K',
        '132K': '_132K',
        '192K': '_192K',
        'HIRES': 'HI_RES',
        'DOLBY': 'DOLBY',
        #视频编码
        'H265' : "HEV",
        'H264' : "AVC",
        'AV1' : "AV1"
    }
    return qualityOfVideoAndAudio[str]

def check_ffmpeg() -> None:
    try:
        subprocess.check_call(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError):
        logging.error("FFmpeg is not installed or not found in PATH. Please install FFmpeg.")
        exit(1)

def sanitize_filename(filename: str) -> str:
    illegal_chars = r'[\\/:*?"<>|\s]'
    sanitized = re.sub(illegal_chars, '_', filename)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_').strip()
    return sanitized[:200] if sanitized else "untitled"

def download_file(url: str, path: str) -> None:
    response = requests.get(url, stream=True,headers=HEADERS)
    total_size = int(response.headers.get("content-length", 0))
    block_size = 1024
    progress_bar = tqdm(total=total_size, unit="iB", unit_scale=True)
    with open(path, "wb") as f:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            f.write(data)
    progress_bar.close()

def mix_streams(videoPath='',audioPath='',outputPath='') ->None:
    '''
        混流

        参数：
        videoPath:临时视频流路径(含文件名)
        audioPath:临时音频流路径(含文件名)
        outputPath:成品路径(含文件名)
    '''
    if (audioPath != '' and videoPath != ''):
        #视频，音频流都存在，即mp4
        audioStream = ffmpeg.input(audioPath)
        videoStream = ffmpeg.input(videoPath)
        outputStream = ffmpeg.output(audioStream, videoStream, outputPath, acodec='copy', vcodec='copy',loglevel='info')
        ffmpeg.run(outputStream)
        os.remove(videoPath)
        os.remove(audioPath)
    elif (audioPath == '' and videoPath != ''):
        #音频视频流，即flv
        inputStream = ffmpeg.input(videoPath)
        outputStream = ffmpeg.output(inputStream, outputPath, vcodec='libx264', loglevel='info')
        ffmpeg.run(outputStream)
        os.remove(videoPath)
    elif (audioPath != '' and videoPath == ''):
        #音频流转mp3
        inputStream = ffmpeg.input(audioPath)
        finalMp3Path = outputPath.replace('.mp4','.mp3')
        outputStream = ffmpeg.output(inputStream, finalMp3Path, loglevel='info')
        ffmpeg.run(outputStream)
        os.remove(audioPath)
