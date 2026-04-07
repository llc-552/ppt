"""
CLIP图像索引模块
使用OpenAI CLIP模型进行图像编码和相似度检索
"""

import os
import torch
import clip
import numpy as np
from PIL import Image
from typing import List, Tuple, Dict, Any
from pathlib import Path

from main.config import get_clip_config


class ClipImageIndexer:
    """CLIP图像索引器
    
    使用CLIP模型对图像进行编码，支持：
    - 图像向量化
    - 文本描述向量化
    - 图文相似度计算
    - 图像相似度检索
    """
    
    def __init__(self):
        """初始化CLIP模型"""
        self.config = get_clip_config()
        self.device = self._get_device()
        self.model, self.preprocess = self._load_model()
        
        print(f"✅ CLIP模型加载成功")
        print(f"   - 模型: {self.config['model_name']}")
        print(f"   - 设备: {self.device}")
        print(f"   - 图像尺寸: {self.config['image_size']}")
    
    def _get_device(self) -> torch.device:
        """获取计算设备"""
        device_config = self.config.get('device', 'cpu')
        if device_config == 'cuda' and torch.cuda.is_available():
            device = torch.device('cuda')
            print(f"   使用 GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = torch.device('cpu')
        return device
    
    def _load_model(self) -> Tuple[Any, Any]:
        """加载CLIP模型"""
        try:
            # CLIP模型名称映射
            model_name = self.config['model_name']
            if 'openai' in model_name.lower():
                # 转换为CLIP库的模型名称
                clip_model_name = model_name.split('/')[-1]
                # 标准CLIP模型：ViT-B/32, ViT-B/16, ViT-L/14等
                if 'vit-base-patch32' in clip_model_name.lower():
                    clip_model_name = 'ViT-B/32'
                elif 'vit-base-patch16' in clip_model_name.lower():
                    clip_model_name = 'ViT-B/16'
                elif 'vit-large' in clip_model_name.lower():
                    clip_model_name = 'ViT-L/14'
            else:
                clip_model_name = 'ViT-B/32'  # 默认模型
            
            model, preprocess = clip.load(clip_model_name, device=self.device)
            model.eval()  # 设置为评估模式
            return model, preprocess
        
        except Exception as e:
            print(f"❌ CLIP模型加载失败: {e}")
            raise
    
    def encode_image(self, image_path: str) -> np.ndarray:
        """编码单张图像
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            图像特征向量 (512维)
        """
        try:
            # 加载并预处理图像
            image = Image.open(image_path).convert('RGB')
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            # 编码图像
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                # L2归一化
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            # 转换为numpy数组
            embedding = image_features.cpu().numpy().flatten()
            return embedding
        
        except Exception as e:
            print(f"❌ 编码图像失败 {image_path}: {e}")
            raise
    
    def encode_images_batch(self, image_paths: List[str], batch_size: int = 32) -> np.ndarray:
        """批量编码图像
        
        Args:
            image_paths: 图像文件路径列表
            batch_size: 批次大小
            
        Returns:
            图像特征矩阵 (N x 512)
        """
        all_embeddings = []
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i + batch_size]
            batch_images = []
            
            # 加载批次图像
            for path in batch_paths:
                try:
                    image = Image.open(path).convert('RGB')
                    image_input = self.preprocess(image)
                    batch_images.append(image_input)
                except Exception as e:
                    print(f"⚠️  跳过无效图像 {path}: {e}")
                    continue
            
            if not batch_images:
                continue
            
            # 批量编码
            batch_tensor = torch.stack(batch_images).to(self.device)
            with torch.no_grad():
                batch_features = self.model.encode_image(batch_tensor)
                batch_features = batch_features / batch_features.norm(dim=-1, keepdim=True)
            
            all_embeddings.append(batch_features.cpu().numpy())
        
        if all_embeddings:
            return np.vstack(all_embeddings)
        else:
            return np.array([])
    
    def encode_text(self, text: str) -> np.ndarray:
        """编码文本描述
        
        Args:
            text: 文本描述
            
        Returns:
            文本特征向量 (512维)
        """
        try:
            # Tokenize文本
            text_input = clip.tokenize([text]).to(self.device)
            
            # 编码文本
            with torch.no_grad():
                text_features = self.model.encode_text(text_input)
                # L2归一化
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            # 转换为numpy数组
            embedding = text_features.cpu().numpy().flatten()
            return embedding
        
        except Exception as e:
            print(f"❌ 编码文本失败: {e}")
            raise
    
    def encode_texts_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码文本
        
        Args:
            texts: 文本列表
            
        Returns:
            文本特征矩阵 (N x 512)
        """
        try:
            # Tokenize所有文本
            text_inputs = clip.tokenize(texts).to(self.device)
            
            # 批量编码
            with torch.no_grad():
                text_features = self.model.encode_text(text_inputs)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            return text_features.cpu().numpy()
        
        except Exception as e:
            print(f"❌ 批量编码文本失败: {e}")
            raise
    
    def compute_similarity(self, image_embedding: np.ndarray, text_embedding: np.ndarray) -> float:
        """计算图文相似度
        
        Args:
            image_embedding: 图像向量
            text_embedding: 文本向量
            
        Returns:
            相似度分数 (0-1)
        """
        # 余弦相似度（已归一化，所以直接点积）
        similarity = np.dot(image_embedding, text_embedding)
        # 转换到0-1范围
        similarity = (similarity + 1) / 2
        return float(similarity)
    
    def rank_images_by_text(self, image_embeddings: np.ndarray, text: str) -> List[Tuple[int, float]]:
        """根据文本描述对图像排序
        
        Args:
            image_embeddings: 图像向量矩阵 (N x 512)
            text: 文本描述
            
        Returns:
            排序后的 [(图像索引, 相似度分数), ...] 列表
        """
        # 编码文本
        text_embedding = self.encode_text(text)
        
        # 计算所有图像与文本的相似度
        similarities = np.dot(image_embeddings, text_embedding)
        
        # 转换到0-1范围并排序
        similarities = (similarities + 1) / 2
        ranked_indices = np.argsort(similarities)[::-1]
        
        results = [(int(idx), float(similarities[idx])) for idx in ranked_indices]
        return results
    
    def find_similar_images(self, query_embedding: np.ndarray, 
                          image_embeddings: np.ndarray, 
                          top_k: int = 5) -> List[Tuple[int, float]]:
        """查找相似图像
        
        Args:
            query_embedding: 查询图像的向量
            image_embeddings: 候选图像向量矩阵
            top_k: 返回top-k个相似图像
            
        Returns:
            [(图像索引, 相似度分数), ...] 列表
        """
        # 计算相似度
        similarities = np.dot(image_embeddings, query_embedding)
        
        # 转换到0-1范围并排序
        similarities = (similarities + 1) / 2
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = [(int(idx), float(similarities[idx])) for idx in top_indices]
        return results
    
    def get_image_metadata(self, image_path: str) -> Dict[str, Any]:
        """获取图像元数据
        
        Args:
            image_path: 图像路径
            
        Returns:
            图像元数据字典
        """
        try:
            image = Image.open(image_path)
            metadata = {
                'width': image.width,
                'height': image.height,
                'format': image.format,
                'mode': image.mode,
                'file_size': os.path.getsize(image_path),
                'filename': os.path.basename(image_path)
            }
            return metadata
        except Exception as e:
            print(f"❌ 获取图像元数据失败: {e}")
            return {}


# 全局单例
_clip_indexer_instance = None

def get_clip_indexer() -> ClipImageIndexer:
    """获取CLIP索引器实例（单例模式）"""
    global _clip_indexer_instance
    if _clip_indexer_instance is None:
        _clip_indexer_instance = ClipImageIndexer()
    return _clip_indexer_instance
