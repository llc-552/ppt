"""
FastAPI 后端接口
提供教学文档智能生成系统的REST API端点
"""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

from main.config import get_storage_config, get_system_config
from main.models import (
    CreateDocumentRequest, GenerateContentRequest, ReviewRequest,
    ExportRequest, APIResponse, AudienceLevel, TeachingDocument
)
from main.workflow import get_workflow
from main.materials import IndexManagementService
from main.export import ExportManager


# ==================== FastAPI应用初始化 ====================

app = FastAPI(
    title="教学文档智能生成系统",
    description="融合LLM、多模态RAG与多智能体协作的教学文档生成平台",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化全局服务
workflow = get_workflow()
material_service = IndexManagementService()
export_manager = ExportManager()
storage_config = get_storage_config()
system_config = get_system_config()


# ==================== 工具函数 ====================

def check_file_size(filename: str, file_size: int) -> bool:
    """检查文件大小"""
    max_size_mb = system_config['max_upload_size']
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes


def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lower().lstrip('.')


def validate_file_format(filename: str, allowed_formats: List[str]) -> bool:
    """验证文件格式"""
    ext = get_file_extension(filename)
    return ext in allowed_formats


# ==================== API端点 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    try:
        with open(Path(__file__).parent / "templates" / "teaching.html", 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return """
        <html>
        <head><title>教学文档智能生成系统</title></head>
        <body style="font-family: Arial, sans-serif; margin: 50px;">
            <h1>教学文档智能生成系统</h1>
            <p>系统正在加载，如果页面长时间不显示，请查看API文档：<a href="/docs">/docs</a></p>
        </body>
        </html>
        """


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ==================== 文档管理接口 ====================

@app.post("/api/documents/create", response_model=APIResponse)
async def create_document(request: CreateDocumentRequest):
    """创建新的教学文档"""
    try:
        doc = workflow.create_document(
            title=request.title,
            topic=request.topic,
            objectives=request.objectives,
            audience_level=request.audience_level.value
        )

        return APIResponse(
            success=True,
            message="文档创建成功",
            data={
                "doc_id": doc.doc_id,
                "title": doc.title,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat()
            }
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/documents/{doc_id}", response_model=APIResponse)
async def get_document(doc_id: str):
    """获取文档详情"""
    try:
        doc = workflow.load_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        return APIResponse(
            success=True,
            message="文档获取成功",
            data={
                "doc_id": doc.doc_id,
                "title": doc.title,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat(),
                "intent": doc.intent.model_dump() if doc.intent else None,
                "ppt_slides_count": len(doc.ppt_content.slides) if doc.ppt_content else 0,
                "export_path": doc.export_path
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/documents", response_model=APIResponse)
async def list_documents():
    """列出所有文档"""
    try:
        documents = workflow.list_documents()
        return APIResponse(
            success=True,
            message="文档列表获取成功",
            data={"documents": documents}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/documents/{doc_id}", response_model=APIResponse)
async def delete_document(doc_id: str):
    """删除文档"""
    try:
        projects_dir = Path(storage_config['projects_dir'])
        doc_path = projects_dir / f"{doc_id}.json"

        if doc_path.exists():
            doc_path.unlink()

        return APIResponse(
            success=True,
            message="文档删除成功"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 材料管理接口 ====================

@app.post("/api/materials/upload-image", response_model=APIResponse)
async def upload_image(
    file: UploadFile = File(...),
    description: str = "",
    tags: str = ""
):
    """上传图像素材"""
    try:
        # 验证文件格式
        if not validate_file_format(file.filename, system_config['supported_image_formats']):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的图像格式。支持的格式: {', '.join(system_config['supported_image_formats'])}"
            )

        # 保存临时文件
        temp_dir = Path(storage_config['temp_dir'])
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename

        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            if not check_file_size(file.filename, len(content)):
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大，最大支持 {system_config['max_upload_size']}MB"
                )
            await f.write(content)

        # 添加到材料库
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        material_id = material_service.add_image_material(
            file_path=str(temp_path),
            description=description,
            tags=tag_list
        )

        return APIResponse(
            success=True,
            message="图像素材上传成功",
            data={
                "material_id": material_id,
                "filename": file.filename
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/materials/upload-document", response_model=APIResponse)
async def upload_document(
    file: UploadFile = File(...),
    description: str = "",
    tags: str = ""
):
    """上传文档素材"""
    try:
        file_ext = get_file_extension(file.filename)

        # 验证文件格式
        if not validate_file_format(file.filename, system_config['supported_doc_formats']):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文档格式。支持的格式: {', '.join(system_config['supported_doc_formats'])}"
            )

        # 保存临时文件
        temp_dir = Path(storage_config['temp_dir'])
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename

        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            if not check_file_size(file.filename, len(content)):
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大，最大支持 {system_config['max_upload_size']}MB"
                )
            await f.write(content)

        # 添加到材料库
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
        material_id = material_service.add_document_material(
            file_path=str(temp_path),
            file_type=file_ext,
            description=description,
            tags=tag_list
        )

        return APIResponse(
            success=True,
            message="文档素材上传成功",
            data={
                "material_id": material_id,
                "filename": file.filename
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/materials/list", response_model=APIResponse)
async def list_materials(material_type: Optional[str] = None, tags: Optional[str] = None):
    """列出素材"""
    try:
        tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else None
        materials = material_service.list_materials(material_type=material_type, tags=tag_list)

        return APIResponse(
            success=True,
            message="素材列表获取成功",
            data={"materials": materials}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/materials/{material_id}", response_model=APIResponse)
async def get_material(material_id: str):
    """获取素材详情"""
    try:
        material = material_service.get_material_by_id(material_id)
        if not material:
            raise HTTPException(status_code=404, detail="素材不存在")

        return APIResponse(
            success=True,
            message="素材获取成功",
            data=material
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 内容生成接口 ====================

@app.post("/api/generate/content", response_model=APIResponse)
async def generate_content(request: GenerateContentRequest, background_tasks: BackgroundTasks):
    """生成教案和PPT内容"""
    try:
        doc = workflow.load_document(request.doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 执行工作流（后台任务）
        background_tasks.add_task(workflow.run_workflow, doc)

        return APIResponse(
            success=True,
            message="内容生成任务已启动，请稍候...",
            data={
                "doc_id": doc.doc_id,
                "status": "running"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 审核接口 ====================

@app.post("/api/review/submit", response_model=APIResponse)
async def submit_review(request: ReviewRequest):
    """提交审核反馈"""
    try:
        doc = workflow.load_document(request.doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 处理审核反馈
        if request.action == "approve":
            doc.status = "approved"
            print(f"✅ 文档 {request.doc_id} 已批准")
        elif request.action == "reject":
            doc.status = "created"
            print(f"❌ 文档 {request.doc_id} 已拒绝")
        elif request.action == "request_changes":
            # 保存修改建议
            if request.comments:
                doc.review_feedback = {
                    "comments": [c.model_dump() for c in request.comments]
                }
            print(f"⚠️  文档 {request.doc_id} 需要修改")

        # 保存文档
        workflow._save_document(doc)

        return APIResponse(
            success=True,
            message=f"审核反馈已提交: {request.action}",
            data={"doc_id": doc.doc_id, "status": doc.status.value}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 导出接口 ====================

@app.post("/api/export", response_model=APIResponse)
async def export_document(request: ExportRequest):
    """导出文档"""
    try:
        doc = workflow.load_document(request.doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        if doc.status.value != "approved":
            raise HTTPException(status_code=400, detail="只有已批准的文档才能导出")

        # 导出文档
        output_path = export_manager.export_document(
            document=doc,
            format=request.format,
            output_path=request.output_path
        )

        return APIResponse(
            success=True,
            message="文档导出成功",
            data={
                "doc_id": doc.doc_id,
                "output_path": output_path,
                "format": request.format
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/download/{doc_id}")
async def download_document(doc_id: str, format: str = "pptx"):
    """下载已导出的文档"""
    try:
        output_dir = Path(storage_config['output_dir'])
        file_path = output_dir / f"{doc_id}.{format}"

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        return FileResponse(
            path=file_path,
            filename=f"{doc_id}.{format}",
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 搜索接口 ====================

@app.post("/api/search/materials")
async def search_materials(query: str):
    """搜索相关素材"""
    try:
        results = material_service.search_by_text(query, k=5)

        return APIResponse(
            success=True,
            message="搜索成功",
            data={"results": results}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 静态文件挂载 ====================

# 挂载静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 挂载模板
templates_dir = Path(__file__).parent / "templates"
if templates_dir.exists():
    app.mount("/templates", StaticFiles(directory=str(templates_dir)), name="templates")


@app.get("/api/config")
async def get_config():
    """获取前端配置"""
    return {
        "api_base": "/api",
        "max_upload_size": system_config['max_upload_size'],
        "supported_image_formats": system_config['supported_image_formats'],
        "supported_doc_formats": system_config['supported_doc_formats']
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)



