import logging
from bilibili_api import video
from src.common.utils import config2reality
from src.common.logger import get_logger
from src.common.models import VideoConfig

class VideoService:
    """处理视频相关的服务"""
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("VideoService初始化成功")
    async def select_stream(self,detecter:video.VideoDownloadURLDataDetecter, video_config:VideoConfig):
        """选择视频和音频流"""
        #将用户输入的配置转化为实际的配置
        videoQuality = config2reality(video_config.video_quality)
        audioQuality = config2reality(video_config.audio_quality)
        codec = config2reality(video_config.codec)
        self.logger.debug(f"用户设置的视频画质:{videoQuality}")
        self.logger.debug(f"用户设置的音频画质:{audioQuality}")
        self.logger.debug(f"用户设置的编码:{codec}")

        streamsList = detecter.detect_all()
        streamsListSize = len(streamsList)
        videoIndex=audioIndex=None
        self.logger.debug(streamsList)

        if (detecter.check_flv_mp4_stream()):
            logging.info('Flv/mp4流,无需选择')
            videoUrl = streamsList[0].url
            return videoUrl, None
        else:
            #遍历流链接列表
            for i in range(streamsListSize):
                if type(streamsList[i]).__name__ == 'VideoStreamDownloadURL':
                    #当前为视频流链接类
                    self.logger.debug(f"当前视频流画质:{streamsList[i].video_quality.name}")
                    self.logger.debug(f"当前视频流解码器:{streamsList[i].video_codecs.name}")
                    if (streamsList[i].video_quality.name == videoQuality) and (streamsList[i].video_codecs.name == codec):
                        videoIndex = i
                elif type(streamsList[i]).__name__ == 'AudioStreamDownloadURL':
                    #当前为音频流链接类
                    self.logger.debug(f"当前音频流画质:{streamsList[i].audio_quality.name}")
                    if streamsList[i].audio_quality.name == audioQuality:
                        audioIndex = i
            self.logger.debug(f"视频流索引:{videoIndex}")
            self.logger.debug(f"音频流索引:{audioIndex}")
            if (videoIndex != None) and (audioIndex != None):
                videoUrl = streamsList[videoIndex].url
                audioUrl = streamsList[audioIndex].url
            else:
                self.logger.warning("设置的清晰度/编码/音质超过了原视频，自动以最佳画质下载")
                streamsList = detecter.detect_best_streams()
                print(streamsList)
                self.logger.debug(f"获取最清晰流链接成功")
                videoUrl = streamsList[0].url
                self.logger.debug(f"v!")
                audioUrl = streamsList[1].url
                self.logger.debug(f"a!")
            self.logger.debug(f"视频流链接:{videoUrl}")
            self.logger.debug(f"音频流链接:{audioUrl}")
            return videoUrl, audioUrl