#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 日志文件
UVICORN_LOG="uvicorn.log"
NGROK_LOG="ngrok.log"

echo "启动 Redis..."
cd "$SCRIPT_DIR/redis/redis-8.0.0"
src/redis-cli -p 6378 shutdown 2>/dev/null
src/redis-server --port 6378 --daemonize yes
cd "$SCRIPT_DIR"

# 自动清理占用 5555 端口的进程
echo "释放 5555 端口..."
fuser -k 5555/tcp 2>/dev/null || true

# 等待端口完全释放
echo "等待端口完全释放..."
sleep 2

# 再次确认端口已释放
for i in {1..10}; do
    if ! lsof -i:5555 > /dev/null 2>&1; then
        echo "✅ 端口 5555 已释放"
        break
    fi
    echo "等待端口释放... ($i/10)"
    sleep 1
done

# 启动 uvicorn，日志同时输出到终端和文件
echo "启动 Uvicorn..."
uvicorn main.app:app --host 0.0.0.0 --port 5555 --reload \
    > >(tee -a $UVICORN_LOG) 2> >(tee -a $UVICORN_LOG >&2) &

UVICORN_PID=$!
echo "✅ Uvicorn 已启动，PID=$UVICORN_PID，日志写入 $UVICORN_LOG"

# 等待 uvicorn 真正启动并监听端口
echo "等待 Uvicorn 完全启动..."
MAX_WAIT=30
for i in $(seq 1 $MAX_WAIT); do
    # 检查进程是否还在运行
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        echo "❌ Uvicorn 启动失败，请查看日志: $UVICORN_LOG"
        tail -20 $UVICORN_LOG
        exit 1
    fi
    
    # 检查端口是否开始监听
    if lsof -i:5555 > /dev/null 2>&1; then
        echo "✅ Uvicorn 已成功监听端口 5555"
        break
    fi
    
    if [ $i -eq $MAX_WAIT ]; then
        echo "❌ Uvicorn 启动超时，请查看日志: $UVICORN_LOG"
        tail -20 $UVICORN_LOG
        kill $UVICORN_PID 2>/dev/null
        exit 1
    fi
    
    sleep 1
done

# 额外等待一秒确保服务完全就绪
sleep 1

# 测试 HTTP 连接
echo "测试本地服务..."
if curl -s http://localhost:5555 > /dev/null; then
    echo "✅ 本地服务响应正常"
else
    echo "⚠️  本地服务可能还未完全就绪，但端口已监听"
fi

# 启动 ngrok，后台运行并记录日志
echo "启动 ngrok 隧道..."

# ngrok authtoken 配置（如果还没配置过，取消下面这行的注释并填入你的 token）
# NGROK_AUTHTOKEN="your_authtoken_here"
# "$SCRIPT_DIR/Ngrok/ngrok" config add-authtoken "$NGROK_AUTHTOKEN"

"$SCRIPT_DIR/Ngrok/ngrok" http 5555 --log="$NGROK_LOG" --log-format=logfmt > /dev/null 2>&1 &

NGROK_PID=$!
echo "✅ ngrok 已启动，PID=$NGROK_PID，日志写入 $NGROK_LOG"

# 等待 ngrok API 可用并获取公网地址
echo "等待 ngrok 生成公网地址..."
for i in {1..30}; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*' | head -n1 | cut -d'"' -f4)
    if [ -n "$NGROK_URL" ]; then
        echo ""
        echo "🌐 =========================================="
        echo "🌐 公网访问地址：$NGROK_URL"
        echo "🌐 本地访问地址：http://localhost:5555"
        echo "🌐 ngrok 控制台：http://localhost:4040"
        echo "🌐 =========================================="
        echo ""
        break
    fi
    sleep 1
done

if [ -z "$NGROK_URL" ]; then
    echo "⚠️  无法获取 ngrok 地址，请手动访问 http://localhost:4040 查看"
fi

# 提示如何停止
echo ""
echo "📝 服务信息："
echo "   Uvicorn PID: $UVICORN_PID"
echo "   ngrok PID: $NGROK_PID"
echo ""
echo "停止服务：kill $UVICORN_PID $NGROK_PID"
echo "或运行：pkill -f uvicorn && pkill -f ngrok"
echo ""
echo "✅ 所有服务已启动完成！"
