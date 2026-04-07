"""
教学文档智能生成系统 - FastAPI启动点
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 导入API模块
from main.api import app as api_app

# 使用api_app作为主应用
app = api_app

# 配置目录
base_dir = Path(__file__).parent.parent
static_dir = base_dir / "main" / "static"

# 挂载静态文件
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 启动事件
@app.on_event("startup")
async def startup_event():
    print("=" * 70)
    print("✅ 教学文档智能生成系统已启动")
    print("=" * 70)
    print("📖 系统功能：")
    print("  1️⃣  教学意图解析智能体")
    print("  2️⃣  索引建立智能体（CLIP图像编码）")
    print("  3️⃣  内容生成智能体")
    print("  4️⃣  模板设计与排版智能体")
    print("  5️⃣  人工审核与导出智能体")
    print()
    print("🌐 访问地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("=" * 70)

@app.on_event("shutdown")
async def shutdown_event():
    print("\n✅ 系统已关闭")

# 健康检查路由
@app.get("/ping")
async def ping():
    return {"status": "pong"}
