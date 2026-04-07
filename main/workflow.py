"""
LangGraph工作流编排
实现5个智能体的协作工作流，包含human-in-the-loop审核机制
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Annotated
from datetime import datetime
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from main.config import get_storage_config
from main.models import (
    TeachingDocument, DocumentStatus, TaskStatus, TaskInfo,
    TeachingIntent, TeachingPlan, PPTContent, PPTLayout, ReviewFeedback
)
from main.agents import (
    IntentParserAgent, ContentGeneratorAgent, LayoutDesignerAgent,
    ImageMatchingAgent, LLMProvider
)
from main.materials import IndexManagementService


# ==================== 工作流状态定义 ====================

class WorkflowState:
    """工作流状态"""

    def __init__(self):
        self.doc_id: str = ""
        self.document: Optional[TeachingDocument] = None
        self.current_step: str = ""
        self.error: Optional[str] = None
        self.progress: int = 0


# ==================== 工作流节点 ====================

class WorkflowNodes:
    """工作流节点集合"""

    def __init__(self):
        """初始化工作流节点"""
        self.intent_parser = IntentParserAgent()
        self.content_generator = ContentGeneratorAgent()
        self.layout_designer = LayoutDesignerAgent()
        self.image_matcher = ImageMatchingAgent()
        self.index_service = IndexManagementService()
        self.llm_provider = LLMProvider()
        self.storage_config = get_storage_config()

    def step_1_parse_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """步骤1: 解析教学意图"""
        try:
            state['current_step'] = 'parse_intent'
            state['progress'] = 10

            doc = state['document']

            # 解析意图
            intent = self.intent_parser.parse_intent(
                topic=doc.title,
                objectives=doc.intent.objectives if doc.intent else [],
                audience_level=doc.intent.audience_level if doc.intent else None
            )

            # 更新文档
            doc.intent = intent
            doc.status = DocumentStatus.INTENT_PARSED
            state['document'] = doc
            state['progress'] = 20

            print(f"✅ 步骤1完成: 教学意图已解析")
            return state
        except Exception as e:
            state['error'] = f"步骤1错误: {str(e)}"
            print(f"❌ {state['error']}")
            raise

    def step_2_generate_content(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """步骤2: 生成教案和PPT内容"""
        try:
            state['current_step'] = 'generate_content'
            state['progress'] = 35

            doc = state['document']

            if not doc.intent:
                raise ValueError("教学意图未设置")

            # 生成教案
            teaching_plan = self.content_generator.generate_teaching_plan(doc.intent)
            doc.teaching_plan = teaching_plan
            state['progress'] = 45

            # 生成PPT内容
            ppt_content = self.content_generator.generate_ppt_content(doc.intent, teaching_plan)
            doc.ppt_content = ppt_content
            doc.status = DocumentStatus.CONTENT_GENERATED
            state['document'] = doc
            state['progress'] = 55

            print(f"✅ 步骤2完成: 教案和PPT内容已生成")
            return state
        except Exception as e:
            state['error'] = f"步骤2错误: {str(e)}"
            print(f"❌ {state['error']}")
            raise

    def step_3_design_layout(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """步骤3: 设计PPT排版"""
        try:
            state['current_step'] = 'design_layout'
            state['progress'] = 60

            doc = state['document']

            if not doc.ppt_content:
                raise ValueError("PPT内容未生成")

            # 获取可用图片
            available_images = self.index_service.list_materials(material_type='image')
            state['progress'] = 65

            # 设计排版
            layout_result = self.layout_designer.design_layout(
                ppt_content=doc.ppt_content,
                template_name='professional',
                available_images=available_images
            )

            # 匹配图片
            image_matches = self.image_matcher.match_images(
                ppt_content=doc.ppt_content,
                available_images=available_images
            )
            state['progress'] = 75
            
            print(f"✅ 图片匹配完成: 为 {len(image_matches)} 张幻灯片匹配了图片")

            # 创建PPT布局，包含图片匹配信息
            from main.models import SlideLayout
            slide_layouts = []
            
            # 创建图片ID映射字典
            image_map = {slide_idx: img_id for slide_idx, img_id in image_matches}
            
            # 为每张幻灯片创建布局信息
            for idx, slide in enumerate(doc.ppt_content.slides):
                image_ids = [image_map[idx]] if idx in image_map else []
                slide_layout = SlideLayout(
                    slide_index=idx,
                    title=slide.title,
                    template=layout_result.get('template', 'professional'),
                    image_ids=image_ids,
                    image_positions=[],
                    text_layout='default'
                )
                slide_layouts.append(slide_layout)
            
            ppt_layout = PPTLayout(
                template_name=layout_result.get('template', 'professional'),
                slides=slide_layouts,
                color_scheme=layout_result.get('color_scheme', 'default'),
                design_quality_score=layout_result.get('design_quality', 0.7)
            )

            doc.ppt_layout = ppt_layout
            doc.status = DocumentStatus.LAYOUT_DESIGNED
            state['document'] = doc
            state['progress'] = 80

            print(f"✅ 步骤3完成: PPT排版已设计")
            return state
        except Exception as e:
            state['error'] = f"步骤3错误: {str(e)}"
            print(f"❌ {state['error']}")
            raise

    def step_4_human_review(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """步骤4: 自动审核 (已禁用人工审核，自动批准)"""
        try:
            state['current_step'] = 'auto_approve'
            state['progress'] = 85

            doc = state['document']
            
            # 跳过人工审核，直接批准
            doc.status = DocumentStatus.APPROVED
            state['document'] = doc
            state['progress'] = 90

            print(f"✅ 步骤4完成: 文档已自动批准")
            return state
        except Exception as e:
            state['error'] = f"步骤4错误: {str(e)}"
            print(f"❌ {state['error']}")
            raise

    def step_5_export_document(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """步骤5: 导出文档"""
        try:
            state['current_step'] = 'export'
            state['progress'] = 95

            doc = state['document']

            if doc.status != DocumentStatus.APPROVED:
                raise ValueError("文档未批准，无法导出")

            # 导出PPT
            from main.export import PPTExporter
            exporter = PPTExporter()

            output_dir = Path(self.storage_config['output_dir'])
            output_dir.mkdir(parents=True, exist_ok=True)

            output_path = output_dir / f"{doc.doc_id}.pptx"
            exporter.export_to_pptx(doc, str(output_path))

            doc.export_path = str(output_path)
            doc.export_format = 'pptx'
            doc.status = DocumentStatus.EXPORTED
            state['document'] = doc
            state['progress'] = 100

            print(f"✅ 步骤5完成: 文档已导出到 {output_path}")
            return state
        except Exception as e:
            state['error'] = f"步骤5错误: {str(e)}"
            print(f"❌ {state['error']}")
            raise

    def handle_error(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """错误处理节点"""
        state['document'].status = DocumentStatus.CREATED
        print(f"❌ 工作流出错: {state.get('error', '未知错误')}")
        return state


# ==================== 工作流管理器 ====================

class TeachingDocWorkflow:
    """教学文档工作流管理器"""

    def __init__(self):
        """初始化工作流"""
        self.nodes = WorkflowNodes()
        self.graph = self._build_graph()
        self.storage_config = get_storage_config()

        # 初始化项目存储
        projects_dir = Path(self.storage_config['projects_dir'])
        projects_dir.mkdir(parents=True, exist_ok=True)

    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流图"""

        # 创建状态图
        graph_builder = StateGraph(dict)

        # 添加节点
        graph_builder.add_node("parse_intent", self.nodes.step_1_parse_intent)
        graph_builder.add_node("generate_content", self.nodes.step_2_generate_content)
        graph_builder.add_node("design_layout", self.nodes.step_3_design_layout)
        graph_builder.add_node("human_review", self.nodes.step_4_human_review)
        graph_builder.add_node("export", self.nodes.step_5_export_document)
        graph_builder.add_node("error_handler", self.nodes.handle_error)

        # 添加边
        graph_builder.add_edge(START, "parse_intent")
        graph_builder.add_edge("parse_intent", "generate_content")
        graph_builder.add_edge("generate_content", "design_layout")
        graph_builder.add_edge("design_layout", "human_review")
        graph_builder.add_edge("human_review", "export")
        graph_builder.add_edge("export", END)

        # 编译图
        return graph_builder.compile()

    def create_document(self, title: str, topic: str, objectives: List[str],
                       audience_level: str = "undergraduate") -> TeachingDocument:
        """创建新文档"""

        doc = TeachingDocument(
            doc_id=f"doc_{uuid.uuid4().hex[:8]}",
            title=title,
            intent=TeachingIntent(
                topic=topic,
                objectives=objectives,
                audience_level=audience_level
            )
        )

        # 保存文档初始状态
        self._save_document(doc)

        print(f"✅ 文档已创建: {doc.doc_id}")
        return doc

    def run_workflow(self, document: TeachingDocument) -> TeachingDocument:
        """运行工作流"""

        print(f"\n{'='*60}")
        print(f"开始工作流: {document.title}")
        print(f"{'='*60}\n")

        # 初始化状态
        state = {
            'doc_id': document.doc_id,
            'document': document,
            'current_step': '',
            'error': None,
            'progress': 0
        }

        try:
            # 执行工作流
            for step_state in self.graph.stream(state):
                state.update(step_state)

            # 返回更新后的文档
            return state['document']

        except Exception as e:
            print(f"❌ 工作流执行失败: {str(e)}")
            state['document'].status = DocumentStatus.CREATED
            self._save_document(state['document'])
            raise

    def _save_document(self, document: TeachingDocument):
        """保存文档到磁盘"""
        try:
            projects_dir = Path(self.storage_config['projects_dir'])
            doc_path = projects_dir / f"{document.doc_id}.json"

            # 序列化文档
            doc_dict = {
                'doc_id': document.doc_id,
                'title': document.title,
                'created_at': document.created_at.isoformat(),
                'updated_at': document.updated_at.isoformat(),
                'status': document.status.value,
                'intent': document.intent.model_dump() if document.intent else None,
                'teaching_plan': document.teaching_plan.model_dump() if document.teaching_plan else None,
                'ppt_content': document.ppt_content.model_dump() if document.ppt_content else None,
                'ppt_layout': document.ppt_layout.model_dump() if document.ppt_layout else None,
                'materials': document.materials,
                'export_path': document.export_path,
                'export_format': document.export_format
            }

            with open(doc_path, 'w', encoding='utf-8') as f:
                json.dump(doc_dict, f, ensure_ascii=False, indent=2, default=str)

            print(f"✅ 文档已保存: {doc_path}")
        except Exception as e:
            print(f"⚠️  保存文档失败: {e}")

    def load_document(self, doc_id: str) -> Optional[TeachingDocument]:
        """从磁盘加载文档"""
        try:
            projects_dir = Path(self.storage_config['projects_dir'])
            doc_path = projects_dir / f"{doc_id}.json"

            if not doc_path.exists():
                return None

            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_dict = json.load(f)

            # 反序列化文档
            document = TeachingDocument(
                doc_id=doc_dict['doc_id'],
                title=doc_dict['title'],
                created_at=datetime.fromisoformat(doc_dict['created_at']),
                updated_at=datetime.fromisoformat(doc_dict['updated_at']),
                status=DocumentStatus(doc_dict['status']),
                materials=doc_dict.get('materials', []),
                export_path=doc_dict.get('export_path'),
                export_format=doc_dict.get('export_format')
            )

            # 恢复intent
            if doc_dict.get('intent'):
                document.intent = TeachingIntent(**doc_dict['intent'])

            # 恢复其他内容
            if doc_dict.get('teaching_plan'):
                document.teaching_plan = TeachingPlan(**doc_dict['teaching_plan'])

            if doc_dict.get('ppt_content'):
                document.ppt_content = PPTContent(**doc_dict['ppt_content'])

            print(f"✅ 文档已加载: {doc_id}")
            return document
        except Exception as e:
            print(f"❌ 加载文档失败: {e}")
            return None

    def list_documents(self) -> List[Dict[str, Any]]:
        """列出所有文档"""
        try:
            projects_dir = Path(self.storage_config['projects_dir'])
            documents = []

            for doc_file in projects_dir.glob('*.json'):
                with open(doc_file, 'r', encoding='utf-8') as f:
                    doc_dict = json.load(f)
                    documents.append({
                        'doc_id': doc_dict['doc_id'],
                        'title': doc_dict['title'],
                        'created_at': doc_dict['created_at'],
                        'status': doc_dict['status']
                    })

            return sorted(documents, key=lambda x: x['created_at'], reverse=True)
        except Exception as e:
            print(f"❌ 列出文档失败: {e}")
            return []


# 全局工作流实例
_workflow_instance = None

def get_workflow() -> TeachingDocWorkflow:
    """获取工作流实例"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = TeachingDocWorkflow()
    return _workflow_instance

