"""
B站视频下载工具 - 服务器入口
"""
import sys
import os

# 确保src目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入服务器运行函数
from src.server.server_core import run_server

if __name__ == "__main__":
    run_server()