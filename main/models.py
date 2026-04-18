"""
数据模型定义
定义教学文档系统的各种数据结构
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ==================== 枚举定义 ====================

class AudienceLevel(str, Enum):
    """受众层级"""
    ELEMENTARY = "elementary"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"


class BloomLevel(str, Enum):
    """Bloom分类法层级"""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class DocumentStatus(str, Enum):
    """文档状态"""
    CREATED = "created"
    INTENT_PARSED = "intent_parsed"
    MATERIALS_UPLOADED = "materials_uploaded"
    CONTENT_GENERATED = "content_generated"
    LAYOUT_DESIGNED = "layout_designed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EXPORTED = "exported"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


# ==================== 教学意图 ====================

class TeachingIntent(BaseModel):
    """教学意图"""
    topic: str = Field(..., description="教学主题")
    objectives: List[str] = Field(..., description="教学目标列表")
    bloom_levels: List[BloomLevel] = Field(default=[], description="Bloom分类法层级")
    audience_level: AudienceLevel = Field(default=AudienceLevel.UNDERGRADUATE, description="受众层级")
    keywords: List[str] = Field(default=[], description="关键词列表")
    duration_minutes: int = Field(default=45, description="课堂时长（分钟）")
    prior_knowledge: Optional[str] = Field(default=None, description="先修知识")
    teaching_style: str = Field(default="balanced", description="教学风格: academic/popular/interactive")
    clarity_score: float = Field(default=0.0, description="意图清晰度评分 (0-1)")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Python数据结构",
                "objectives": ["了解列表的基本操作", "掌握字典的使用"],
                "bloom_levels": ["understand", "apply"],
                "audience_level": "high_school",
                "keywords": ["列表", "字典", "数据结构"],
                "duration_minutes": 45,
                "teaching_style": "interactive"
            }
        }


# ==================== 素材管理 ====================

class MaterialMetadata(BaseModel):
    """素材元数据"""
    material_id: str = Field(..., description="素材ID")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型: image/document")
    content_type: str = Field(..., description="MIME类型")
    file_size: int = Field(..., description="文件大小（字节）")
    upload_time: datetime = Field(default_factory=datetime.now, description="上传时间")
    description: Optional[str] = Field(default=None, description="描述")
    tags: List[str] = Field(default=[], description="标签")
    vector_embedding: Optional[List[float]] = Field(default=None, description="向量嵌入")


class ImageMaterial(MaterialMetadata):
    """图像素材"""
    width: int = Field(..., description="图像宽度")
    height: int = Field(..., description="图像高度")
    clip_embedding: Optional[List[float]] = Field(default=None, description="CLIP向量嵌入")


class DocumentMaterial(MaterialMetadata):
    """文档素材"""
    text_content: str = Field(..., description="文本内容")
    chunks: List[Dict[str, Any]] = Field(default=[], description="文本分块")


# ==================== PPT内容 ====================

class SlideKeyPoints(BaseModel):
    """幻灯片关键点"""
    title: str = Field(..., description="标题")
    key_points: List[str] = Field(..., description="要点列表")
    speaker_notes: Optional[str] = Field(default=None, description="说话稿")
    image_descriptions: List[str] = Field(default=[], description="图像描述（用于图像检索）")
    teaching_tips: Optional[str] = Field(default=None, description="教学提示")


class PPTContent(BaseModel):
    """PPT内容结构"""
    title: str = Field(..., description="演示文稿标题")
    subtitle: str = Field(..., description="副标题")
    slides: List[SlideKeyPoints] = Field(..., description="幻灯片列表")
    outline: Optional[str] = Field(default=None, description="课程大纲")
    conclusion: Optional[str] = Field(default=None, description="总结")
    learning_outcomes: List[str] = Field(default=[], description="学习成果")
    assessment: Optional[str] = Field(default=None, description="评估方法")


# ==================== 教案 ====================

class TeachingPlan(BaseModel):
    """教案"""
    topic: str = Field(..., description="主题")
    objectives: List[str] = Field(..., description="教学目标")
    introduction: str = Field(..., description="导入")
    content: str = Field(..., description="正文内容")
    key_points: List[str] = Field(..., description="重点难点")
    teaching_methods: List[str] = Field(default=[], description="教学方法")
    classroom_activities: Optional[str] = Field(default=None, description="课堂活动")
    homework: Optional[str] = Field(default=None, description="课堂作业")
    assessment_methods: Optional[str] = Field(default=None, description="评估方法")
    resources: List[str] = Field(default=[], description="教学资源")


# ==================== 排版设计 ====================

class SlideLayout(BaseModel):
    """幻灯片排版信息"""
    slide_index: int = Field(..., description="幻灯片索引")
    title: str = Field(..., description="标题")
    template: str = Field(..., description="使用的模板")
    image_ids: List[str] = Field(default=[], description="插入的图像ID列表")
    image_positions: List[Dict[str, Any]] = Field(default=[], description="图像位置信息")
    text_layout: str = Field(default="default", description="文本布局")
    design_notes: Optional[str] = Field(default=None, description="设计备注")


class PPTLayout(BaseModel):
    """整个PPT的排版设计"""
    template_name: str = Field(..., description="使用的模板名称")
    slides: List[SlideLayout] = Field(..., description="各幻灯片排版")
    color_scheme: str = Field(default="default", description="配色方案")
    font_style: str = Field(default="default", description="字体风格")
    design_quality_score: float = Field(default=0.0, description="设计质量评分 (0-1)")


# ==================== 审核与反馈 ====================

class ReviewComment(BaseModel):
    """审核注释"""
    slide_index: int = Field(..., description="幻灯片索引")
    section: str = Field(..., description="审核部分: title/content/image/layout")
    comment: str = Field(..., description="评论内容")
    suggestion: Optional[str] = Field(default=None, description="修改建议")
    priority: str = Field(default="medium", description="优先级: low/medium/high")


class ReviewFeedback(BaseModel):
    """审核反馈"""
    overall_quality_score: float = Field(..., description="整体质量评分 (0-1)")
    comments: List[ReviewComment] = Field(default=[], description="审核注释列表")
    approval_status: str = Field(default="pending", description="审批状态: pending/approved/rejected")
    modifications_needed: List[str] = Field(default=[], description="需要修改的项目列表")
    reviewer_notes: Optional[str] = Field(default=None, description="审核人员备注")


# ==================== 任务与项目 ====================

class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    progress: int = Field(default=0, description="进度 (0-100)")
    current_step: str = Field(default="", description="当前步骤")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间")


class TeachingDocument(BaseModel):
    """教学文档（项目主体）"""
    doc_id: str = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    status: DocumentStatus = Field(default=DocumentStatus.CREATED, description="文档状态")

    # 工作流各步骤的输出
    intent: Optional[TeachingIntent] = Field(default=None, description="教学意图")
    teaching_plan: Optional[TeachingPlan] = Field(default=None, description="教案")
    ppt_content: Optional[PPTContent] = Field(default=None, description="PPT内容")
    ppt_layout: Optional[PPTLayout] = Field(default=None, description="PPT排版设计")

    # 素材相关
    materials: List[str] = Field(default=[], description="关联的素材ID列表")

    # 审核相关
    review_feedback: Optional[ReviewFeedback] = Field(default=None, description="审核反馈")

    # 导出相关
    export_path: Optional[str] = Field(default=None, description="导出文件路径")
    export_format: Optional[str] = Field(default="pptx", description="导出格式: pptx/pdf/md")

    # 任务跟踪
    current_task: Optional[TaskInfo] = Field(default=None, description="当前任务")


# ==================== API请求/响应 ====================

class CreateDocumentRequest(BaseModel):
    """创建文档请求"""
    title: str = Field(..., description="文档标题")
    topic: str = Field(..., description="教学主题")
    objectives: List[str] = Field(..., description="教学目标")
    audience_level: AudienceLevel = Field(default=AudienceLevel.UNDERGRADUATE, description="受众层级")


class GenerateContentRequest(BaseModel):
    """生成内容请求"""
    doc_id: str = Field(..., description="文档ID")
    regenerate: bool = Field(default=False, description="是否重新生成")
    custom_instructions: Optional[str] = Field(default=None, description="自定义指令")


class ReviewRequest(BaseModel):
    """审核请求"""
    doc_id: str = Field(..., description="文档ID")
    action: str = Field(..., description="操作: approve/reject/request_changes")
    comments: List[ReviewComment] = Field(default=[], description="审核注释")


class ExportRequest(BaseModel):
    """导出请求"""
    doc_id: str = Field(..., description="文档ID")
    format: str = Field(default="pptx", description="导出格式: pptx/pdf/md")
    output_path: Optional[str] = Field(default=None, description="输出路径")


class PPTRevisionRequest(BaseModel):
    """PPT对话式修改请求"""
    doc_id: str = Field(..., description="文档ID")
    instruction: str = Field(..., description="用户修改指令")
    conversation_history: List[Dict[str, str]] = Field(default=[], description="历史对话")


class APIResponse(BaseModel):
    """API通用响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="响应数据")


class StreamingEvent(BaseModel):
    """流式事件"""
    event_type: str = Field(..., description="事件类型: progress/token/node/done/error")
    content: Optional[str] = Field(default=None, description="事件内容")
    progress: Optional[int] = Field(default=None, description="进度百分比")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="元数据")
