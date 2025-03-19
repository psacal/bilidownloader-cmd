import questionary
import yaml
from pathlib import Path

# ================= 主逻辑 =================
def generate_config():
    """配置生成主流程（逐问题获取方式）"""
    print("欢迎使用Bilibili下载器配置生成工具！")

    # 1. 选择配置类型
    config_type = questionary.select(
        "请选择要生成的配置类型（客户端用于下载任务，服务端用于远程服务）:",
        choices=[
            {'name': '客户端配置', 'value': 'client'},
            {'name': '服务端配置', 'value': 'server'}
        ]
    ).ask()

    # 初始化配置字典
    config = {}


    config['log_level'] = questionary.select(
        "选择日志等级:\nDEBUG - 调试信息\nINFO - 正常信息\nWARNING - 警告信息\nERROR - 错误信息\nCRITICAL - 严重错误",
        choices=[
            {'name': 'DEBUG (调试信息)', 'value': 'DEBUG'},
            {'name': 'INFO (正常信息)', 'value': 'INFO'},
            {'name': 'WARNING (警告)', 'value': 'WARNING'},
            {'name': 'ERROR (错误)', 'value': 'ERROR'},
            {'name': 'CRITICAL (严重错误)', 'value': 'CRITICAL'}
        ]
    ).ask()

    config['log_dir'] = questionary.path(
        "输入日志目录路径（默认为项目根目录下的log文件夹）:",
        default=str(Path.cwd() / 'log'),
        validate=lambda path: Path(path).parent.exists()
    ).ask()

    if config_type == 'client':
        print("\n🔧 正在设置客户端配置...")
        config['download_dir'] = questionary.path(
            "下载文件保存目录（默认为项目根目录下的download目录）:",
            default=str(Path.cwd() / 'download'),
            validate=lambda path: Path(path).parent.exists()
        ).ask()

        config['cache_dir'] = questionary.path(
            "临时文件缓存目录（默认为项目根目录下的cache目录）:",
            default=str(Path.cwd() / 'cache'),
            validate=lambda path: Path(path).parent.exists()
        ).ask()

        config['video_quality'] = questionary.select(
            "选择视频清晰度:\n360P: 流畅 | 480P: 清晰 | 720P: 高清\n1080P: 全高清 | 1080P_PLUS: 全高清Plus\n1080P_60: 全高清60帧 | 4K: 超清4K\nHDR: HDR真彩 | DOLBY: 杜比视界 | 8K: 超高清8K",
            choices=[
                {'name': '360P (流畅)', 'value': '360P'},
                {'name': '480P (清晰)', 'value': '480P'},
                {'name': '720P (高清)', 'value': '720P'},
                {'name': '1080P (全高清)', 'value': '1080P'},
                {'name': '1080P_PLUS', 'value': '1080P_PLUS'},
                {'name': '1080P_60 (60帧)', 'value': '1080P_60'},
                {'name': '4K (超清)', 'value': '4K'},
                {'name': 'HDR (真彩)', 'value': 'HDR'},
                {'name': 'DOLBY (杜比视界)', 'value': 'DOLBY'},
                {'name': '8K (超高清)', 'value': '8K'}
            ]
        ).ask()

        config['audio_quality'] = questionary.select(
            "选择音频质量:\n64K: 流畅 | 132K: 标准\n192K: 高品质 | HIRES: Hi-Res无损\nDOLBY: 杜比全景声",
            choices=[
                {'name': '64K (流畅)', 'value': '64K'},
                {'name': '132K (标准)', 'value': '132K'},
                {'name': '192K (高品质)', 'value': '192K'},
                {'name': 'HIRES (无损)', 'value': 'HIRES'},
                {'name': 'DOLBY (全景声)', 'value': 'DOLBY'}
            ]
        ).ask()

        config['codec'] = questionary.select(
            "选择视频编码（H264默认 | H265高效 | AV1新一代）:",
            choices=[
                {'name': 'H264 (AVC编码)', 'value': 'H264'},
                {'name': 'H265 (HEVC编码)', 'value': 'H265'},
                {'name': 'AV1 (新一代编码)', 'value': 'AV1'}
            ]
        ).ask()

        config['max_workers'] = questionary.text(
            "并发下载线程数（默认为3，建议范围1-10）:",
            default='3',
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 10
        ).ask()

        config['threads'] = questionary.text(
            "单任务线程数（默认为4，建议范围1-16）:",
            default='4',
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 16
        ).ask()

        config['audio_only'] = questionary.confirm(
            "是否仅下载音频?",
            default=False
        ).ask()

    else:
        print("\n🔧 正在设置服务端配置...")
        config['host'] = questionary.text(
            "服务器监听地址（建议使用 0.0.0.0 允许外部访问）:",
            default='0.0.0.0'
        ).ask()

        config['port'] = questionary.text(
            "服务器监听端口（有效端口范围：1-65535）:",
            default='8000',
            validate=lambda x: x.isdigit() and 1 <= int(x) <= 65535
        ).ask()

    # 4. 保存配置
    save_path = questionary.path(
        "配置文件保存路径（支持绝对路径或相对路径）:",
        default=str(Path.cwd() / f'{config_type}_config.yaml'),
        validate=lambda path: Path(path).parent.exists()
    ).ask()

    with open(save_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    print(f"✅ 配置文件已生成到：{save_path}")

if __name__ == '__main__':
    generate_config()