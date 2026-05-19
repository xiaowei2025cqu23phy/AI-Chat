#!/usr/bin/env python3
# run.py - 启动脚本

import os
import sys

# 设置环境变量
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

# 添加当前目录到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# API Key — 必须通过环境变量或 .env 文件设置
if "DEEPSEEK_API_KEY" not in os.environ:
    env_path = os.path.join(script_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
    if "DEEPSEEK_API_KEY" not in os.environ:
        print("⚠️  未设置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填入密钥")
        sys.exit(1)

# 导入并运行主程序
from deepseek_pro import main

if __name__ == "__main__":
    main()
