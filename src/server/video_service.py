import logging
from bilibili_api import video
from src.common.utils import config2reality

class VideoService:
    """处理视频相关的服务"""
    
    @staticmethod
    async def select_stream(detecter, video_config):
        """选择视频和音频流"""
        #将用户输入的配置转化为实际的配置
        videoQuality = config2reality(video_config.video_quality)
        audioQuality = config2reality(video_config.audio_quality)
        codec = config2reality(video_config.codec)
        logging.debug(f"用户设置的视频画质:{videoQuality}")
        logging.debug(f"用户设置的音频画质:{audioQuality}")
        logging.debug(f"用户设置的编码:{codec}")

        streamsList = detecter.detect_all()
        streamsListSize = len(streamsList)
        videoIndex=audioIndex=None
        logging.debug(streamsList)

        if (detecter.check_flv_mp4_stream()):
            logging.info('Flv/mp4流,无需选择')
            videoUrl = streamsList[0].url
            return videoUrl, None
        else:
            #遍历流链接列表
            for i in range(streamsListSize):
                if type(streamsList[i]).__name__ == 'VideoStreamDownloadURL':
                    #当前为视频流链接类
                    logging.debug(f"当前视频流画质:{streamsList[i].video_quality.name}")
                    logging.debug(f"当前视频流解码器:{streamsList[i].video_codecs.name}")
                    if (streamsList[i].video_quality.name == videoQuality) and (streamsList[i].video_codecs.name == codec):
                        videoIndex = i
                elif type(streamsList[i]).__name__ == 'AudioStreamDownloadURL':
                    #当前为音频流链接类
                    logging.debug(f"当前音频流画质:{streamsList[i].audio_quality.name}")
                    if streamsList[i].audio_quality.name == audioQuality:
                        audioIndex = i
            logging.debug(f"视频流索引:{videoIndex}")
            logging.debug(f"音频流索引:{audioIndex}")
            if (videoIndex != None) and (audioIndex != None):
                videoUrl = streamsList[videoIndex].url
                audioUrl = streamsList[audioIndex].url
            else:
                logging.warning("设置的清晰度/编码/音质超过了原视频，自动以最佳画质下载")
                streamsList = detecter.detect_best_streams()
                print(streamsList)
                logging.debug(f"获取最清晰流链接成功")
                videoUrl = streamsList[0].url
                logging.debug(f"v!")
                audioUrl = streamsList[1].url
                logging.debug(f"a!")
            logging.debug(f"视频流链接:{videoUrl}")
            logging.debug(f"音频流链接:{audioUrl}")
            return videoUrl, audioUrl