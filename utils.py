import re
import os
import logging
import aiohttp
import asyncio
import ffmpeg
import subprocess
import bilibili_api
from bilibili_api import HEADERS,login_v2
import tqdm
from questionary import Validator, ValidationError
def extract_bvid(url_or_code: str) -> str:
    '''
    从输入中提取BV号，支持以下格式：
    1. 纯数字（作为AV号处理）
    2. 以av/AV开头的AV号
    3. 以BV/bv开头的BV号
    返回：
        str: 标准化的BV号
        None: 输入格式不正确
    '''
    if not url_or_code:
        return None
        
    # 匹配模式
    avid_pattern = re.compile(r'[aA][vV](\d+)')
    bvid_pattern = re.compile(r'[bB][vV][\d\w]+')
    number_pattern = re.compile(r'^\d+$')
    
    # 尝试匹配AV号
    avid_match = avid_pattern.search(url_or_code)
    if avid_match:
        try:
            return bilibili_api.aid2bvid(int(avid_match.group(1)))
        except ValueError:
            logging.error("AV号格式不正确")
            return None
            
    # 尝试匹配BV号
    bvid_match = bvid_pattern.search(url_or_code)
    if bvid_match:
        bvid = bvid_match.group(0)
        if bvid.startswith(('Bv', 'bV', 'bv')):
            return 'BV' + bvid[2:]
        return bvid
        
    # 尝试匹配纯数字（作为AV号处理）
    number_match = number_pattern.search(url_or_code)
    if number_match:
        try:
            return bilibili_api.aid2bvid(int(number_match.group(0)))
        except ValueError:
            logging.error("AV号格式不正确")
            return None
            
    return None

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

async def download_file(url: str, path: str) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            total_size = int(response.headers.get("content-length", 0))
            block_size = 1024 * 1024  # 使用更大的块大小
            progress_bar = tqdm(total=total_size, unit="iB", unit_scale=True)
            
            with open(path, "wb") as f:
                async for chunk in response.content.iter_chunked(block_size):
                    progress_bar.update(len(chunk))
                    f.write(chunk)
            progress_bar.close()

async def mix_streams(videoPath='', audioPath='', outputPath='') -> None:
    '''
        混流
    '''
    try:
        # 创建输出目录（如果不存在）
        os.makedirs(os.path.dirname(outputPath), exist_ok=True)
        
        # 构建FFmpeg命令
        if videoPath and audioPath:
            # 视频和音频都存在，进行混流
            stream = ffmpeg.input(videoPath)
            audio = ffmpeg.input(audioPath)
            stream = ffmpeg.output(stream, audio, outputPath, acodec='copy', vcodec='copy')
        elif videoPath:
            # 只有视频，直接复制
            stream = ffmpeg.input(videoPath)
            stream = ffmpeg.output(stream, outputPath, c='copy')
        elif audioPath:
            # 只有音频，直接复制
            stream = ffmpeg.input(audioPath)
            stream = ffmpeg.output(stream, outputPath, c='copy')
        else:
            raise ValueError("至少需要提供一个输入文件")
        
        # 运行FFmpeg命令
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        
        # 删除临时文件
        if videoPath and os.path.exists(videoPath):
            os.remove(videoPath)
        if audioPath and os.path.exists(audioPath):
            os.remove(audioPath)
            
    except ffmpeg.Error as e:
        logging.error(f"FFmpeg错误: {e.stderr.decode() if e.stderr else str(e)}")
        raise
    except Exception as e:
        logging.error(f"混流错误: {str(e)}")
        raise
class CountryCodeValidator(Validator):
    def validate(self, document):
        code = document.text
        # 业务逻辑验证
        try:
            if not login_v2.have_code(code):
                raise ValidationError(
                    message="无效的国家代码", 
                    cursor_position=len(code)
                )
        except ValueError:  # 如果验证失败抛出异常
            raise ValidationError(
                message="非法代码格式",
                cursor_position=len(code)
            )