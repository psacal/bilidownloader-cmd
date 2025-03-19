#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频下载工具 - 命令行客户端入口
"""
import sys
import os

# 确保src目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# 导入客户端CLI
from src.client.cli import cli

if __name__ == "__main__":
    cli()