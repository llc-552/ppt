"""
多智能体模块
实现教学文档系统的5个核心智能体
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from main.config import get_llm_config, get_teaching_doc_config, get_system_config
from main.models import (
    TeachingIntent, TeachingPlan, PPTContent, SlideKeyPoints,
    AudienceLevel, BloomLevel
)


class LLMProvider:
    """LLM提供者 - 统一管理LLM调用"""

    _instance = None
    _llm = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMProvider, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._llm is None:
            self._init_llm()

    def _init_llm(self):
        """初始化LLM"""
        config = get_llm_config()
        
        # 配置 HTTP 客户端以支持代理
        http_client = None
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        
        if http_proxy or https_proxy:
            # 使用 HTTP/HTTPS 代理而不是 SOCKS
            proxy_url = https_proxy or http_proxy
            # 确保只使用 http/https 协议，忽略 socks
            if proxy_url.startswith('socks://'):
                print(f"⚠️  警告: 检测到 socks 代理 ({proxy_url})，但 ChatOpenAI 不支持，将跳过代理")
                http_client = httpx.Client(trust_env=False)
            else:
                # trust_env=False 防止 httpx 从环境变量读取 ALL_PROXY (socks)
                http_client = httpx.Client(proxy=proxy_url, trust_env=False)
                print(f"✅ 使用代理: {proxy_url}")
        
        # 临时移除 ALL_PROXY 环境变量，避免 ChatOpenAI 验证时读取 socks 代理
        all_proxy_backup = os.environ.pop('ALL_PROXY', None)
        all_proxy_lower_backup = os.environ.pop('all_proxy', None)
        
        try:
            self._llm = ChatOpenAI(
                api_key=config['api_key'],
                base_url=config['api_base'],
                model=config['model'],
                temperature=config['temperature'],
                max_tokens=config['max_tokens'],
                http_client=http_client
            )
            print(f"✅ LLM提供者初始化成功: {config['model']}")
        finally:
            # 恢复 ALL_PROXY 环境变量
            if all_proxy_backup:
                os.environ['ALL_PROXY'] = all_proxy_backup
            if all_proxy_lower_backup:
                os.environ['all_proxy'] = all_proxy_lower_backup

    def get_llm(self):
        """获取LLM实例"""
        return self._llm

    def chat(self, system_prompt: str, user_message: str) -> str:
        """对话接口"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        response = self._llm.invoke(messages)
        return response.content


# ==================== Agent 1: 教学意图解析智能体 ====================

class IntentParserAgent:
    """教学意图解析智能体

    职责：
    - 理解教师输入的教学主题、教学目标与受众层次
    - 提取关键词和Bloom分类
    - 评估意图清晰度
    """

    def __init__(self):
        """初始化意图解析智能体"""
        self.llm_provider = LLMProvider()
        self.teaching_config = get_teaching_doc_config()

    def parse_intent(self,
                     topic: str,
                     objectives: List[str],
                     audience_level: AudienceLevel = AudienceLevel.UNDERGRADUATE,
                     additional_context: str = "") -> TeachingIntent:
        """解析教学意图"""

        # 构建提示词
        system_prompt = """你是一个教学设计专家。你的任务是分析教师的教学意图，并提取关键信息。
        
输出应该是一个JSON对象，包含以下字段：
- keywords: 关键词列表（5-10个）
- bloom_levels: Bloom分类法层级列表（remember/understand/apply/analyze/evaluate/create）
- teaching_style: 教学风格（academic/popular/interactive）
- clarity_score: 意图清晰度评分（0-1）
- improvements: 改进建议（如果有的话）

请注意：
1. 根据目标的表述来判断Bloom层级
2. 清晰度评分：表述越具体、目标越明确，分数越高
3. 教学风格：根据学科和受众层级建议
"""

        user_message = f"""分析以下教学意图：

主题：{topic}
目标：
{chr(10).join(f"- {obj}" for obj in objectives)}
受众层级：{audience_level.value}
{f'额外信息：{additional_context}' if additional_context else ''}

请进行详细分析。"""

        response = self.llm_provider.chat(system_prompt, user_message)

        # 解析响应
        try:
            # 尝试提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)
            else:
                analysis = {}
        except json.JSONDecodeError:
            analysis = {}

        # 构建TeachingIntent对象
        intent = TeachingIntent(
            topic=topic,
            objectives=objectives,
            audience_level=audience_level,
            keywords=analysis.get('keywords', self._extract_keywords(topic, objectives)),
            bloom_levels=[BloomLevel(b) for b in analysis.get('bloom_levels', ['understand'])],
            teaching_style=analysis.get('teaching_style', 'balanced'),
            clarity_score=analysis.get('clarity_score', 0.5)
        )

        print(f"✅ 教学意图解析完成: {intent.topic}")
        return intent

    def _extract_keywords(self, topic: str, objectives: List[str]) -> List[str]:
        """提取关键词的备用方法"""
        # 简单的关键词提取
        all_text = topic + " " + " ".join(objectives)
        words = all_text.split()
        # 过滤短词
        keywords = [w for w in words if len(w) > 2][:10]
        return keywords


# ==================== Agent 2: 内容生成智能体 ====================

class ContentGeneratorAgent:
    """内容生成智能体

    职责：
    - 利用LLM撰写教案正文与PPT要点
    - 包含教学目标、重点难点、课堂作业等
    - 支持多种教学风格
    """

    def __init__(self):
        """初始化内容生成智能体"""
        self.llm_provider = LLMProvider()
        self.teaching_config = get_teaching_doc_config()

    def generate_teaching_plan(self, intent: TeachingIntent) -> TeachingPlan:
        """生成教案"""

        system_prompt = """你是一位经验丰富的教学设计师。你要根据教学意图，生成一份详细的教案。
        
��案应包含：
1. 清晰的教学目标
2. 引人入胜的导入
3. 逻辑清晰的正文内容
4. 清楚的重点难点
5. 多样的教学方法
6. 交互式课堂活动
7. 明确的课堂作业
8. 有效的评估方法

输出格式应为JSON对象，包含所有这些元素。
"""

        user_message = f"""根据以下教学意图生成详细教案：

主题：{intent.topic}
教学目标：
{chr(10).join(f"- {obj}" for obj in intent.objectives)}
受众层级：{intent.audience_level.value}
教学风格：{intent.teaching_style}
关键词：{', '.join(intent.keywords)}

请生成完整的教案。"""

        response = self.llm_provider.chat(system_prompt, user_message)

        # 解析响应
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                plan_data = json.loads(json_str)
            else:
                plan_data = {}
        except json.JSONDecodeError:
            plan_data = {}

        # 构建TeachingPlan对象
        plan = TeachingPlan(
            topic=intent.topic,
            objectives=intent.objectives,
            introduction=plan_data.get('introduction', ''),
            content=plan_data.get('content', ''),
            key_points=plan_data.get('key_points', []),
            teaching_methods=plan_data.get('teaching_methods', []),
            classroom_activities=plan_data.get('classroom_activities', ''),
            homework=plan_data.get('homework', ''),
            assessment_methods=plan_data.get('assessment_methods', ''),
            resources=plan_data.get('resources', [])
        )

        print(f"✅ 教案生成完成: {plan.topic}")
        return plan

    def generate_ppt_content(self, intent: TeachingIntent, teaching_plan: TeachingPlan) -> PPTContent:
        """生成PPT内容"""

        system_prompt = """你是一位PPT专家。你要根据教案内容，生成一份结构化的PPT大纲。
        
PPT应该：
1. 包含5-10张幻灯片
2. 每张幻灯片有清晰的标题和3-5个关键要点
3. 包含说话稿（speaker notes）
4. 每张幻灯片可能需要哪种类型的图片
5. 包含教学提示

输出为JSON格式，包含：
- title: PPT标题（字符串）
- subtitle: 副标题（字符串）
- slides: 幻灯片数组，每个包含title, key_points, speaker_notes, image_descriptions, teaching_tips
- outline: 课程大纲（字符串）
- conclusion: 总结（字符串）
- learning_outcomes: 学习成果（字符串数组）
- assessment: 评估方法（字符串，多个方法用换行符分隔）
"""

        user_message = f"""根据以下教案生成PPT内容大纲：

教案标题：{teaching_plan.topic}
教学目标：{chr(10).join(f"- {obj}" for obj in teaching_plan.objectives)}

正文内容：
{teaching_plan.content}

重点难点：
{chr(10).join(f"- {kp}" for kp in teaching_plan.key_points)}

课堂活动：
{teaching_plan.classroom_activities or '默认互动'}

课堂作业：
{teaching_plan.homework or '默认作业'}

请生成一份精心设计的PPT大纲。"""

        response = self.llm_provider.chat(system_prompt, user_message)

        # 解析响应
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                ppt_data = json.loads(json_str)
            else:
                ppt_data = {}
        except json.JSONDecodeError:
            ppt_data = {}

        # 构建SlideKeyPoints列表
        slides = []
        for slide_data in ppt_data.get('slides', []):
            # 确保 image_descriptions 是列表类型
            image_descs = slide_data.get('image_descriptions', [])
            if isinstance(image_descs, str):
                # 如果是字符串，转换为包含单个元素的列表
                image_descs = [image_descs] if image_descs else []
            
            slide = SlideKeyPoints(
                title=slide_data.get('title', ''),
                key_points=slide_data.get('key_points', []),
                speaker_notes=slide_data.get('speaker_notes', ''),
                image_descriptions=image_descs,
                teaching_tips=slide_data.get('teaching_tips', '')
            )
            slides.append(slide)

        # 如果没���生成幻灯片，创建默认幻灯片
        if not slides:
            slides = self._create_default_slides(intent, teaching_plan)

        # 构建PPTContent对象
        # 处理assessment字段：如果是列表，转换为字符串
        assessment_value = ppt_data.get('assessment', teaching_plan.assessment_methods)
        if isinstance(assessment_value, list):
            assessment_value = '\n'.join(assessment_value)
        
        ppt_content = PPTContent(
            title=intent.topic,
            subtitle=ppt_data.get('subtitle', ''),
            slides=slides,
            outline=ppt_data.get('outline', ''),
            conclusion=ppt_data.get('conclusion', ''),
            learning_outcomes=ppt_data.get('learning_outcomes', intent.objectives),
            assessment=assessment_value
        )

        print(f"✅ PPT内容生成完成: {len(slides)} 张幻灯片")
        return ppt_content

    def _create_default_slides(self, intent: TeachingIntent, teaching_plan: TeachingPlan) -> List[SlideKeyPoints]:
        """创建默认幻灯片"""
        slides = [
            SlideKeyPoints(
                title="标题页",
                key_points=[intent.topic],
                image_descriptions=["教学主题的相关图片"]
            ),
            SlideKeyPoints(
                title="学习目标",
                key_points=intent.objectives,
                image_descriptions=["目标相关的图片"]
            ),
            SlideKeyPoints(
                title="主要内容",
                key_points=teaching_plan.key_points[:5],
                image_descriptions=["内容示意图"],
                speaker_notes=teaching_plan.content[:200]
            ),
            SlideKeyPoints(
                title="课堂活动",
                key_points=["积极参与", "分组讨论", "实践操作"],
                image_descriptions=["课堂活动相关图片"],
                speaker_notes=teaching_plan.classroom_activities or ""
            ),
            SlideKeyPoints(
                title="总结",
                key_points=["回顾关键点", "强化学习成果"],
                image_descriptions=["总结相关图片"],
                speaker_notes=teaching_plan.content[-200:]
            )
        ]
        return slides


# ==================== Agent 3: 模板设计与排版智能体 ====================

class LayoutDesignerAgent:
    """模板设计与排版智能体

    职责：
    - 选择合适的PPT模板
    - 规划幻灯片版面
    - 推荐图片位置和大小
    - 应用设计规则
    """

    def __init__(self):
        """初始化排版设计智能体"""
        self.llm_provider = LLMProvider()

    def design_layout(self,
                      ppt_content: PPTContent,
                      template_name: str = "professional",
                      available_images: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """设计PPT排版"""

        available_images = available_images or []

        system_prompt = """你是一位PPT设计专家。你要为PPT设计版面布局和配图方案。
        
对于每张幻灯片，提供：
1. 推荐的设计布局
2. 适合的图片位置（top/center/bottom/left/right）
3. 配色建议
4. 字体建议
5. 设计评分（0-1）

输出为JSON格式。
"""

        slides_summary = "\n".join([
            f"- 幻灯片{i+1}: {slide.title}\n  关键点: {', '.join(slide.key_points[:3])}\n  需要图片: {', '.join(slide.image_descriptions[:2])}"
            for i, slide in enumerate(ppt_content.slides)
        ])

        user_message = f"""为以下PPT设计版面：

模板风格：{template_name}
主题：{ppt_content.title}

幻灯片列表：
{slides_summary}

可用图片数量：{len(available_images)}

请为每张幻灯片设计详细的排版方案。"""

        response = self.llm_provider.chat(system_prompt, user_message)

        # 解析响应
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                layout_data = json.loads(json_str)
            else:
                layout_data = {}
        except json.JSONDecodeError:
            layout_data = {}

        return {
            'template': template_name,
            'slides_layout': layout_data.get('slides', []),
            'color_scheme': layout_data.get('color_scheme', 'professional'),
            'design_quality': layout_data.get('design_quality', 0.7)
        }


# ==================== Agent 4: 内容检索与图片匹配智能体 ====================

class ImageMatchingAgent:
    """图片匹配智能体

    职责：
    - 根据幻灯片内容描述检索相关图片
    - 评估图片与内容的匹配度
    - 推荐最佳图片位置
    """

    def __init__(self):
        """初始化图片匹配智能体"""
        self.llm_provider = LLMProvider()
        self.system_config = get_system_config()

    def match_images(self,
                     ppt_content: PPTContent,
                     available_images: List[Dict[str, Any]]) -> List[Tuple[int, str]]:
        """为幻灯片匹配图片

        返回：[(slide_index, image_id), ...]
        """

        matches = []

        for slide_idx, slide in enumerate(ppt_content.slides):
            if not slide.image_descriptions:
                continue

            # 从可用图片中选��最匹配的
            best_image_id = None
            best_score = 0

            for image in available_images:
                # 这里可以计算内容与图片的匹配度
                # 简化版本：检查标签
                image_tags = image.get('tags', [])
                slide_keywords = slide.key_points + slide.image_descriptions

                # 计算匹配分数
                score = sum(1 for tag in image_tags if any(tag.lower() in kw.lower() for kw in slide_keywords))

                if score > best_score:
                    best_score = score
                    best_image_id = image.get('material_id')

            if best_image_id:
                matches.append((slide_idx, best_image_id))

        return matches

