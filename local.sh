#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 启动 Redis
cd ./redis/redis-8.0.0
src/redis-cli -p 6378 shutdown 2>/dev/null
src/redis-server --port 6378 --daemonize yes
cd "$SCRIPT_DIR"

# 启动 Uvicorn
uvicorn main.app:app --reload --port 3367
