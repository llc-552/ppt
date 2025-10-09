# 📦 项目清理指南

在将项目推送到 GitHub 之前，请按照本指南清理不需要的文件。

## ⚠️ 必须删除的文件

这些文件包含敏感信息或不应提交到版本控制：

### 1. 配置文件
```bash
# 包含 API Key 的配置文件
rm config.yaml
# ✅ 保留: config.example.yaml（示例文件）
```

### 2. 日志文件
```bash
rm -f *.log
rm -f ngrok.log
rm -f uvicorn.log
rm -rf redis/*.log
```

### 3. 临时文件和脚本
```bash
# 删除临时测试文件
rm -f test.py
rm -f s.py
rm -f 2.sh
rm -f local.sh

# 删除 ngrok 相关（如果有敏感信息）
rm -f ngrok.sh
rm -rf Ngrok/
```

### 4. Redis 数据文件
```bash
# 删除 Redis 数据库文件
rm -f redis/*.rdb
rm -f redis/*.aof
rm -f redis/dump*.rdb

# 删除 Redis 源码包（如果有）
rm -f redis/redis-*.tar.gz
rm -rf redis/redis-*/
```

### 5. Python 缓存
```bash
# 删除 Python 缓存
rm -rf __pycache__/
rm -rf */__pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

### 6. FAISS 索引（可选）
```bash
# 如果索引文件很大或包含敏感数据
rm -rf faiss_index/*
# 用户可以在首次运行时自动生成
```

## 🔍 可选删除的文件

根据你的需求决定是否删除：

### RAG 数据
```bash
# 如果 rag_data 包含版权或敏感文档
rm -rf rag_data/*
# 建议：保留一个示例文档
```

### 静态资源
```bash
# 如果图片文件很大
# ls -lh static/*.png
# 根据需要删除
```

## ✅ 应该保留的文件

这些文件是项目必需的：

```
✅ app.py
✅ vet.py
✅ animal_hospital.py
✅ rag.py
✅ chatstore.py
✅ prompt.py
✅ config.py
✅ config.example.yaml  (示例配置)
✅ requirements.txt
✅ README.md
✅ CONFIG_README.md
✅ CONTRIBUTING.md
✅ DEPLOYMENT.md
✅ LICENSE
✅ .gitignore
✅ start.sh
✅ start.bat
✅ templates/
✅ static/
```

## 🚀 一键清理脚本

### Linux/Mac

创建并运行清理脚本：

```bash
cat > cleanup.sh << 'EOF'
#!/bin/bash
echo "🧹 清理项目文件..."

# 删除配置文件
rm -f config.yaml

# 删除日志
rm -f *.log
rm -f redis/*.log

# 删除临时文件
rm -f test.py s.py 2.sh local.sh

# 删除 Redis 数据
rm -f redis/*.rdb redis/*.aof redis/dump*.rdb
rm -f redis/redis-*.tar.gz
rm -rf redis/redis-*/

# 删除 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# 删除 FAISS 索引（可选）
# rm -rf faiss_index/*

# 删除 ngrok 相关
rm -f ngrok.sh ngrok.log
rm -rf Ngrok/

echo "✅ 清理完成！"
echo ""
echo "📋 下一步："
echo "1. 检查 .gitignore 文件"
echo "2. 创建 config.yaml 从 config.example.yaml"
echo "3. 运行: git status"
EOF

chmod +x cleanup.sh
./cleanup.sh
```

### Windows

创建 `cleanup.bat`：

```batch
@echo off
echo 🧹 清理项目文件...

del /f config.yaml 2>nul
del /f *.log 2>nul
del /f redis\*.log 2>nul
del /f test.py s.py 2.sh local.sh 2>nul
del /f redis\*.rdb redis\*.aof redis\dump*.rdb 2>nul
del /f ngrok.sh ngrok.log 2>nul

for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"

echo ✅ 清理完成！
pause
```

## 🔒 安全检查清单

在推送前确认：

- [ ] `config.yaml` 已删除或在 `.gitignore` 中
- [ ] 所有日志文件已删除
- [ ] 没有硬编码的 API Key
- [ ] Redis 数据文件已删除
- [ ] Python 缓存已清理
- [ ] `.gitignore` 文件配置正确

## 📝 验证步骤

1. **检查 Git 状态**
   ```bash
   git status
   ```

2. **查看将要提交的文件**
   ```bash
   git add .
   git status
   ```

3. **检查是否有敏感信息**
   ```bash
   git diff --cached
   ```

4. **确认 .gitignore 生效**
   ```bash
   git check-ignore -v config.yaml
   # 应该显示: .gitignore:X:config.yaml
   ```

## 📤 推送到 GitHub

清理完成后：

```bash
# 初始化 Git（如果还没有）
git init

# 添加文件
git add .

# 查看状态
git status

# 提交
git commit -m "Initial commit: Veta Animal Hospital System"

# 添加远程仓库
git remote add origin https://github.com/yourusername/veta.git

# 推送
git push -u origin main
```

## 🔄 持续维护

推送后：

1. **定期更新依赖**
   ```bash
   pip list --outdated
   ```

2. **检查安全漏洞**
   ```bash
   pip-audit
   ```

3. **保持文档同步**
   - 功能更新时更新 README
   - API 变更时更新文档

## ❓ 常见问题

**Q: 不小心提交了敏感信息怎么办？**

A: 使用 git-filter-repo 或 BFG Repo-Cleaner 清理历史记录：
```bash
# 从历史中删除文件
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch config.yaml" \
  --prune-empty --tag-name-filter cat -- --all
```

**Q: .gitignore 不生效？**

A: 清除 Git 缓存：
```bash
git rm -r --cached .
git add .
git commit -m "Update .gitignore"
```

---

完成清理后，你的项目就可以安全地推送到 GitHub 了！🎉



