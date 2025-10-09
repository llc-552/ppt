#!/bin/bash
echo "🧹 清理项目文件..."

# 删除配置文件
rm -f config.yaml

# 删除日志
rm -f *.log
rm -f redis/*.log 2>/dev/null

# 删除临时文件
rm -f test.py s.py 2.sh local.sh

# 删除 Redis 数据
rm -f redis/*.rdb redis/*.aof redis/dump*.rdb 2>/dev/null
rm -f redis/redis-*.tar.gz 2>/dev/null
rm -rf redis/redis-*/ 2>/dev/null

# 删除 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# 删除 ngrok 相关
rm -f ngrok.sh ngrok.log
rm -rf Ngrok/ 2>/dev/null

echo "✅ 清理完成！"
echo ""
echo "📋 下一步："
echo "1. 检查 .gitignore 文件"
echo "2. 从 config.example.yaml 创建 config.yaml"
echo "3. 运行: git status"
