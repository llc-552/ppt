"""
配置管理模块
用于读取和管理应用配置
"""

import os
import yaml
from typing import Dict, Any


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
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        支持点号分隔的嵌套键，例如: 'openai.api_key'
        
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
    
    def get_openai_config(self) -> Dict[str, Any]:
        """获取 OpenAI 配置"""
        return {
            'api_base': self.get('openai.api_base'),
            'api_key': self.get('openai.api_key'),
            'model': self.get('openai.model'),
            'temperature': self.get('openai.temperature', 0.9)
        }
    
    def get_redis_config(self) -> Dict[str, Any]:
        """获取 Redis 配置"""
        return {
            'host': self.get('redis.host', '127.0.0.1'),
            'port': self.get('redis.port', 6378)
        }
    
    def get_rag_config(self) -> Dict[str, Any]:
        """获取 RAG 配置"""
        return {
            'folder_path': self.get('rag.folder_path', './rag_data'),
            'index_path': self.get('rag.index_path', './faiss_index'),
            'embedding_model': self.get('rag.embedding_model', 'Qwen/Qwen3-Embedding-0.6B'),
            'rerank_model': self.get('rag.rerank_model', 'BAAI/bge-reranker-base'),
            'bm25_k': self.get('rag.bm25_k', 5),
            'faiss_k': self.get('rag.faiss_k', 5),
            'top_n': self.get('rag.top_n', 1),
            'chunk_size': self.get('rag.chunk_size', 500),
            'chunk_overlap': self.get('rag.chunk_overlap', 50),
            'device': self.get('rag.device', 'cpu')
        }
    
    def get_vetchat_config(self) -> Dict[str, Any]:
        """获取 VetChat 配置"""
        return {
            'max_tokens': self.get('vetchat.max_tokens', 384),
            'max_summary_tokens': self.get('vetchat.max_summary_tokens', 128),
            'trim_max_tokens': self.get('vetchat.trim_max_tokens', 2500)
        }
    
    def reload(self):
        """重新加载配置文件"""
        self._config_data = None
        self._load_config()


# 创建全局配置实例
config = Config()


# 便捷函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置项的便捷函数"""
    return config.get(key, default)


def get_openai_config() -> Dict[str, Any]:
    """获取 OpenAI 配置的便捷函数"""
    return config.get_openai_config()


def get_redis_config() -> Dict[str, Any]:
    """获取 Redis 配置的便捷函数"""
    return config.get_redis_config()


def get_rag_config() -> Dict[str, Any]:
    """获取 RAG 配置的便捷函数"""
    return config.get_rag_config()


def get_vetchat_config() -> Dict[str, Any]:
    """获取 VetChat 配置的便捷函数"""
    return config.get_vetchat_config()


if __name__ == "__main__":
    # 测试配置读取
    print("=" * 60)
    print("测试配置读取")
    print("=" * 60)
    
    print("\n1. OpenAI 配置:")
    print(get_openai_config())
    
    print("\n2. Redis 配置:")
    print(get_redis_config())
    
    print("\n3. RAG 配置:")
    print(get_rag_config())
    
    print("\n4. VetChat 配置:")
    print(get_vetchat_config())
    
    print("\n5. 获取单个配置项:")
    print(f"OpenAI API Key: {get_config('openai.api_key')}")
    print(f"Redis Host: {get_config('redis.host')}")

