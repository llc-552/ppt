"""
素材管理模块
处理图片和文档的上传、索引和检索
"""

import os
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from PIL import Image
import numpy as np
import faiss
from rank_bm25 import BM25Okapi
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from main.config import get_config, get_storage_config, get_clip_config, get_embedding_config
from main.models import MaterialMetadata, ImageMaterial, DocumentMaterial
from main.clip_indexer import get_clip_indexer


class ImageIndexer:
    """图像索引器 - 使用CLIP模型处理图片"""

    def __init__(self):
        """初始化图像索引器"""
        self.storage_config = get_storage_config()
        # 使用全局CLIP索引器
        self.clip_indexer = get_clip_indexer()

    def process_image(self, image_path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """处理图像并生成CLIP向量"""
        try:
            # 使用CLIP编码图像
            embedding = self.clip_indexer.encode_image(image_path)
            
            # 获取图像元数据
            metadata = self.clip_indexer.get_image_metadata(image_path)

            return embedding, metadata
        except Exception as e:
            print(f"❌ 处理图像 {image_path} 失败: {e}")
            raise


class DocumentIndexer:
    """文档索引器 - 处理PDF和文本文档"""

    def __init__(self):
        """初始化文档索引器"""
        self.embedding_config = get_embedding_config()
        self.storage_config = get_storage_config()

        # 初始化embedding模型
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_config['text_model'],
            model_kwargs={'device': self.embedding_config['device']}
        )

        # 初始化文本分割器
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.embedding_config['chunk_size'],
            chunk_overlap=self.embedding_config['chunk_overlap'],
            separators=["\n\n", "\n", "。", "！", "？", "，", ""]
        )

        print(f"✅ 文档索引器初始化成功")

    def process_document(self, file_path: str, file_type: str = "pdf") -> Tuple[str, List[Dict[str, Any]]]:
        """处理文档并进行分块"""
        try:
            # 加载文档
            if file_type == "pdf":
                loader = PyPDFLoader(file_path)
                documents = loader.load()
                text = '\n'.join([doc.page_content for doc in documents])
            elif file_type in ["txt", "md"]:
                loader = TextLoader(file_path, encoding='utf-8')
                documents = loader.load()
                text = documents[0].page_content if documents else ""
            else:
                raise ValueError(f"不支持的文件类型: {file_type}")

            # 分块
            chunks = self.splitter.split_text(text)

            # 生成向量
            chunk_data = []
            for i, chunk in enumerate(chunks):
                try:
                    embedding = self.embeddings.embed_query(chunk)
                    chunk_data.append({
                        'chunk_id': f"{hashlib.md5(chunk.encode()).hexdigest()[:8]}",
                        'text': chunk,
                        'embedding': embedding,
                        'length': len(chunk)
                    })
                except Exception as e:
                    print(f"⚠️  向量化分块 {i} 失败: {e}")
                    continue

            print(f"✅ 文档处理成功: {len(chunk_data)} 个分块")
            return text, chunk_data
        except Exception as e:
            print(f"❌ 处理文档 {file_path} 失败: {e}")
            raise


class IndexManagementService:
    """索引管理服务"""

    def __init__(self):
        """初始化索引管理服务"""
        self.storage_config = get_storage_config()
        self.embedding_config = get_embedding_config()

        # 创建必要的目录
        self.materials_dir = Path(self.storage_config['materials_dir'])
        self.index_dir = Path(self.storage_config['index_dir'])
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # 初始化索引器
        self.image_indexer = ImageIndexer()
        self.document_indexer = DocumentIndexer()

        # 初始化Faiss索引
        self.faiss_index = None
        self.metadata_list = []
        self.bm25_corpus = []
        self.bm25 = None

        self._load_or_create_index()

    def _load_or_create_index(self):
        """加载或创建Faiss索引"""
        index_path = self.index_dir / 'faiss_index.idx'
        metadata_path = self.index_dir / 'metadata.json'

        if index_path.exists() and metadata_path.exists():
            try:
                self.faiss_index = faiss.read_index(str(index_path))
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata_list = json.load(f)
                print(f"✅ 加载现有索引: {len(self.metadata_list)} 个向量")
            except Exception as e:
                print(f"⚠️  加载索引失败: {e}，创建新索引")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        """创建新的Faiss索引"""
        # 初始化一个空的Faiss索引（512维向量）
        self.faiss_index = faiss.IndexFlatL2(512)
        self.metadata_list = []
        self.bm25_corpus = []
        print("✅ 创建新的 Faiss 索引")

    def add_image_material(self, file_path: str, description: str = "", tags: List[str] = None) -> str:
        """添加图像素材"""
        try:
            # 处理图像
            embedding, img_metadata = self.image_indexer.process_image(file_path)

            # 生成素材ID
            material_id = f"img_{uuid.uuid4().hex[:8]}"

            # 保存图像文件到素材库
            filename = os.path.basename(file_path)
            dest_path = self.materials_dir / filename
            Image.open(file_path).save(str(dest_path))

            # 创建元数据
            metadata = {
                'material_id': material_id,
                'type': 'image',
                'filename': filename,
                'file_path': str(dest_path),
                'description': description,
                'tags': tags or [],
                'upload_time': datetime.now().isoformat(),
                'width': img_metadata['width'],
                'height': img_metadata['height'],
                'embedding_dim': len(embedding)
            }

            # 添加到Faiss索引
            embedding = np.array([embedding], dtype=np.float32)
            self.faiss_index.add(embedding)
            self.metadata_list.append(metadata)

            # 保存索引
            self._save_index()

            print(f"✅ 图像素材添加成功: {material_id}")
            return material_id
        except Exception as e:
            print(f"❌ 添加图像素材失败: {e}")
            raise

    def add_document_material(self, file_path: str, file_type: str, description: str = "", tags: List[str] = None) -> str:
        """添加文档素材"""
        try:
            # 处理文档
            text_content, chunks = self.document_indexer.process_document(file_path, file_type)

            # 生成素材ID
            material_id = f"doc_{uuid.uuid4().hex[:8]}"

            # 保存文档文件
            filename = os.path.basename(file_path)
            dest_path = self.materials_dir / filename
            with open(dest_path, 'rb') as src:
                with open(dest_path, 'wb') as dst:
                    dst.write(src.read())

            # 创建元数据
            metadata = {
                'material_id': material_id,
                'type': 'document',
                'filename': filename,
                'file_path': str(dest_path),
                'file_type': file_type,
                'description': description,
                'tags': tags or [],
                'upload_time': datetime.now().isoformat(),
                'text_length': len(text_content),
                'chunk_count': len(chunks)
            }

            # 添加所有分块到Faiss索引和BM25
            for chunk in chunks:
                embedding = np.array([chunk['embedding']], dtype=np.float32)
                self.faiss_index.add(embedding)

                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_id'] = chunk['chunk_id']
                chunk_metadata['chunk_text'] = chunk['text']
                self.metadata_list.append(chunk_metadata)

                # 分词用于BM25
                self.bm25_corpus.append(chunk['text'].split())

            # 重建BM25索引
            if self.bm25_corpus:
                self.bm25 = BM25Okapi(self.bm25_corpus)

            # 保存索引
            self._save_index()

            print(f"✅ 文档素材添加成功: {material_id}")
            return material_id
        except Exception as e:
            print(f"❌ 添加文档素材失败: {e}")
            raise

    def search_by_text(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """通过文本查询检索相关素材"""
        if self.faiss_index is None or len(self.metadata_list) == 0:
            return []

        try:
            # 对查询文本进行向量化
            embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_config['text_model'],
                model_kwargs={'device': self.embedding_config['device']}
            )
            query_embedding = embeddings.embed_query(query)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            # Faiss相似度搜索
            distances, indices = self.faiss_index.search(query_embedding, k)

            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self.metadata_list):
                    results.append(self.metadata_list[idx])

            return results
        except Exception as e:
            print(f"❌ 检索失败: {e}")
            return []

    def search_by_similarity(self, image_path: str, k: int = 5) -> List[Dict[str, Any]]:
        """通过图像检索相关素材"""
        if self.faiss_index is None or len(self.metadata_list) == 0:
            return []

        try:
            # 处理查询图像
            query_embedding, _ = self.image_indexer.process_image(image_path)
            query_embedding = np.array([query_embedding], dtype=np.float32)

            # Faiss相似度搜索
            distances, indices = self.faiss_index.search(query_embedding, k)

            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self.metadata_list):
                    results.append(self.metadata_list[idx])

            return results
        except Exception as e:
            print(f"❌ 检索失败: {e}")
            return []

    def _save_index(self):
        """保存Faiss索引和元数据"""
        try:
            index_path = self.index_dir / 'faiss_index.idx'
            metadata_path = self.index_dir / 'metadata.json'

            if self.faiss_index:
                faiss.write_index(self.faiss_index, str(index_path))

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata_list, f, ensure_ascii=False, indent=2, default=str)

            print(f"✅ 索引已保存")
        except Exception as e:
            print(f"❌ 保存索引失败: {e}")

    def get_material_by_id(self, material_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取素材"""
        for metadata in self.metadata_list:
            if metadata.get('material_id') == material_id:
                return metadata
        return None

    def list_materials(self, material_type: str = None, tags: List[str] = None) -> List[Dict[str, Any]]:
        """列出素材"""
        results = []
        for metadata in self.metadata_list:
            if material_type and metadata.get('type') != material_type:
                continue
            if tags and not any(tag in metadata.get('tags', []) for tag in tags):
                continue
            results.append(metadata)
        return results

