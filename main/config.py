"""
配置管理模块
用于读取和管理应用配置
"""

import os
import yaml
from typing import Dict, Any, List


class Config:
    """配置管理类"""
    
    _instance = None
    _config_data = None
    
    def __new__(cls):
        """单例模式，确保只有一个配置实例"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置"""
        if self._config_data is None:
            self._load_config()
            self._ensure_directories()

    def _load_config(self):
        """加载配置文件"""
        # 获取配置文件路径（从项目根目录查找，而不是从 main 目录）
        # __file__ 是 main/config.py，我们需要往上一级找到项目根目录
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),  # 往上一级到项目根目录
            'config.yaml'
        )
        
        # 检查配置文件是否存在
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                f"请创建 config.yaml 配置文件"
            )
        
        # 读取配置文件
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            print(f"✅ 配置文件加载成功: {config_path}")
        except Exception as e:
            raise Exception(f"配置文件读取失败: {e}")
    
    def _ensure_directories(self):
        """确保所有必要的目录存在"""
        dirs = [
            self.get('storage.data_dir'),
            self.get('storage.projects_dir'),
            self.get('storage.materials_dir'),
            self.get('storage.index_dir'),
            self.get('storage.output_dir'),
            self.get('storage.temp_dir'),
        ]

        for dir_path in dirs:
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        支持点号分隔的嵌套键，例如: 'llm.api_key'

        Args:
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值
            
        Returns:
            配置值
        """
        if self._config_data is None:
            self._load_config()
        
        # 处理嵌套键
        keys = key.split('.')
        value = self._config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    # LLM 配置
    def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置"""
        return {
            'api_base': self.get('llm.api_base'),
            'api_key': self.get('llm.api_key'),
            'model': self.get('llm.model'),
            'temperature': self.get('llm.temperature', 0.7),
            'max_tokens': self.get('llm.max_tokens', 4096)
        }

    # CLIP 配置
    def get_clip_config(self) -> Dict[str, Any]:
        """获取 CLIP 配置"""
        return {
            'model_name': self.get('clip.model_name', 'openai/clip-vit-base-patch32'),
            'device': self.get('clip.device', 'cpu'),
            'image_size': self.get('clip.image_size', 224)
        }

    # Embedding 配置
    def get_embedding_config(self) -> Dict[str, Any]:
        """获取 Embedding 配置"""
        return {
            'text_model': self.get('embedding.text_model', 'Qwen/Qwen3-Embedding-0.6B'),
            'rerank_model': self.get('embedding.rerank_model', 'BAAI/bge-reranker-base'),
            'bm25_k': self.get('embedding.bm25_k', 5),
            'faiss_k': self.get('embedding.faiss_k', 5),
            'top_n': self.get('embedding.top_n', 3),
            'chunk_size': self.get('embedding.chunk_size', 500),
            'chunk_overlap': self.get('embedding.chunk_overlap', 50),
            'device': self.get('embedding.device', 'cpu')
        }

    # 存储配置
    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置"""
        return {
            'data_dir': self.get('storage.data_dir', './data'),
            'projects_dir': self.get('storage.projects_dir', './data/projects'),
            'materials_dir': self.get('storage.materials_dir', './data/materials'),
            'index_dir': self.get('storage.index_dir', './data/faiss_index'),
            'output_dir': self.get('storage.output_dir', './data/outputs'),
            'temp_dir': self.get('storage.temp_dir', './data/temp')
        }

    # 模板配置
    def get_template_config(self) -> Dict[str, Any]:
        """获取模板配置"""
        return {
            'preset_dir': self.get('templates.preset_dir', './templates/presets'),
            'default_template': self.get('templates.default_template', 'professional'),
            'available_templates': self.get('templates.available_templates', ['professional', 'educational', 'creative'])
        }

    # 系统配置
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return {
            'debug': self.get('system.debug', False),
            'max_upload_size': self.get('system.max_upload_size', 100),
            'supported_doc_formats': self.get('system.supported_doc_formats', ['pdf', 'docx', 'txt', 'md']),
            'supported_image_formats': self.get('system.supported_image_formats', ['jpg', 'jpeg', 'png', 'gif', 'webp']),
            'image_relevance_threshold': self.get('system.image_relevance_threshold', 0.5),
            'content_quality_threshold': self.get('system.content_quality_threshold', 0.7)
        }

    # 教学文档配置
    def get_teaching_doc_config(self) -> Dict[str, Any]:
        """获取教学文档配置"""
        return {
            'max_pages': self.get('teaching_doc.max_pages', 50),
            'max_words_per_page': self.get('teaching_doc.max_words_per_page', 300),
            'default_audience_level': self.get('teaching_doc.default_audience_level', 'undergraduate'),
            'audience_levels': self.get('teaching_doc.audience_levels', ['elementary', 'middle_school', 'high_school', 'undergraduate', 'graduate']),
            'bloom_levels': self.get('teaching_doc.bloom_levels', ['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'])
        }
    
    # Redis 配置
    def get_redis_config(self) -> Dict[str, Any]:
        """获取 Redis 配置"""
        return {
            'host': self.get('redis.host', '127.0.0.1'),
            'port': self.get('redis.port', 6379),
            'db': self.get('redis.db', 0),
            'enabled': self.get('redis.enabled', False)
        }
    
    def reload(self):
        """重新加载配置文件"""
        self._config_data = None
        self._load_config()
        self._ensure_directories()


# 创建全局配置实例
config = Config()


# 便捷函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置项的便捷函数"""
    return config.get(key, default)


def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置的便捷函数"""
    return config.get_llm_config()


def get_clip_config() -> Dict[str, Any]:
    """获取 CLIP 配置的便捷函数"""
    return config.get_clip_config()


def get_embedding_config() -> Dict[str, Any]:
    """获取 Embedding 配置的便捷函数"""
    return config.get_embedding_config()


def get_storage_config() -> Dict[str, Any]:
    """获取存储配置的便捷函数"""
    return config.get_storage_config()


def get_template_config() -> Dict[str, Any]:
    """获取模板配置的便捷函数"""
    return config.get_template_config()


def get_system_config() -> Dict[str, Any]:
    """获取系统配置的便捷函数"""
    return config.get_system_config()


def get_teaching_doc_config() -> Dict[str, Any]:
    """获取教学文档配置的便捷函数"""
    return config.get_teaching_doc_config()


def get_redis_config() -> Dict[str, Any]:
    """获取 Redis 配置的便捷函数"""
    return config.get_redis_config()


if __name__ == "__main__":
    # 测试配置读取
    print("=" * 60)
    print("测试配置读取")
    print("=" * 60)
    
    print("\n1. LLM 配置:")
    print(get_llm_config())

    print("\n2. CLIP 配置:")
    print(get_clip_config())

    print("\n3. Embedding 配置:")
    print(get_embedding_config())

    print("\n4. 存储配置:")
    print(get_storage_config())

    print("\n5. 教学文档配置:")
    print(get_teaching_doc_config())
