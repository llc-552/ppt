#!/usr/bin/env python
"""
教学文档智能生成系统启动脚本
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 70)
    print("🎓 教学文档智能生成系统")
    print("融合LLM、多模态RAG与多智能体协作的教学文档生成平台")
    print("=" * 70 + "\n")

    # 启动服务器
    uvicorn.run(
        "main.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

