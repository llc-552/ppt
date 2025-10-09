import os
import json
import hashlib
from tqdm import tqdm
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain.docstore.document import Document
from main.config import get_rag_config

class Retriever:
    def __init__(
        self,
        folder_path: str,
        embedding_model: str = "Qwen/Qwen3-Embedding-0.6B",
        rerank_model: str = "BAAI/bge-reranker-base",
        index_path: str = "./faiss_index",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        bm25_k: int = 5,
        faiss_k: int = 5,
        top_n: int = 3,
        device: str = "cpu"
    ):
        self.folder_path = folder_path
        self.index_path = index_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.bm25_k = bm25_k
        self.faiss_k = faiss_k
        self.top_n = top_n

        # 初始化Embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            encode_kwargs={"normalize_embeddings": True},
            model_kwargs={"device": device}
        )

        # 检查是否需要重建索引
        need_rebuild = self._need_rebuild_index()

        if need_rebuild:
            print("开始构建/重建索引...")
            self._build_index()
            print("索引构建完成！")
        else:
            print("RAG初始化，使用现有索引...")

        # 加载文档用于BM25（无论是否重建都需要）
        self._load_documents_for_bm25()

        # 加载FAISS向量库
        self.faiss_vectorstore = FAISS.load_local(
            self.index_path,
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        self.faiss_retriever = self.faiss_vectorstore.as_retriever(search_kwargs={"k": faiss_k})

        # 构建BM25检索器
        texts = [doc.page_content for doc in self.docs]
        self.bm25_retriever = BM25Retriever.from_texts(
            texts,
            metadatas=[doc.metadata for doc in self.docs]
        )
        self.bm25_retriever.k = bm25_k

        # 混合检索器
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.faiss_retriever],
            weights=[0.5, 0.5]
        )

        # Reranker
        self.rerank_model = HuggingFaceCrossEncoder(model_name=rerank_model)
        self.compressor = CrossEncoderReranker(model=self.rerank_model, top_n=top_n)
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.compressor,
            base_retriever=self.ensemble_retriever
        )

    def _calculate_folder_hash(self, folder_path: str) -> str:
        """计算文件夹中所有文件的哈希值，用于检测文件变化"""
        file_hashes = []
        
        if not os.path.exists(folder_path):
            return ""
        
        # 获取文件夹中所有支持的文件
        for file in sorted(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, file)
            if not os.path.isfile(file_path):
                continue
                
            ext = os.path.splitext(file)[-1].lower()
            if ext not in [".pdf", ".txt", ".docx", ".doc", ".md"]:
                continue
                
            # 计算文件的哈希值（包含文件名和修改时间）
            stat = os.stat(file_path)
            file_info = f"{file}:{stat.st_size}:{stat.st_mtime}"
            file_hash = hashlib.md5(file_info.encode()).hexdigest()
            file_hashes.append(file_hash)
        
        # 计算整个文件夹的哈希值
        folder_hash = hashlib.md5("".join(file_hashes).encode()).hexdigest()
        return folder_hash

    def _save_index_metadata(self, folder_hash: str):
        """保存索引元数据"""
        metadata = {
            "folder_hash": folder_hash,
            "folder_path": self.folder_path,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_model": getattr(self.embeddings, 'model_name', "unknown")
        }
        
        metadata_path = os.path.join(self.index_path, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _load_index_metadata(self) -> dict:
        """加载索引元数据"""
        metadata_path = os.path.join(self.index_path, "metadata.json")
        if not os.path.exists(metadata_path):
            return {}
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def _need_rebuild_index(self) -> bool:
        """检查是否需要重建索引"""
        # 如果索引目录不存在，需要构建
        if not os.path.exists(self.index_path):
            return True
        
        # 计算当前文件夹哈希值
        current_hash = self._calculate_folder_hash(self.folder_path)
        
        # 加载之前的元数据
        metadata = self._load_index_metadata()
        
        # 如果没有元数据或哈希值不匹配，需要重建
        if not metadata or metadata.get("folder_hash") != current_hash:
            print(f"检测到文件变化，需要重建索引")
            return True
        
        # 检查参数是否变化
        if (metadata.get("chunk_size") != self.chunk_size or 
            metadata.get("chunk_overlap") != self.chunk_overlap):
            print(f"检测到切分参数变化，需要重建索引")
            return True
        
        #print(f"文件未发生变化，使用现有索引")
        return False

    def _load_documents(self):
        """加载文档的通用方法"""
        documents = []
        for file in os.listdir(self.folder_path):
            file_path = os.path.join(self.folder_path, file)
            if not os.path.isfile(file_path):
                continue

            ext = os.path.splitext(file)[-1].lower()

            try:
                if ext == ".pdf":
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                elif ext == ".txt":
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs = loader.load()
                elif ext in [".docx", ".doc"]:
                    loader = UnstructuredWordDocumentLoader(file_path)
                    docs = loader.load()
                elif ext == ".md":
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs = loader.load()
                else:
                    print(f"跳过不支持的文件: {file}")
                    continue
            except Exception as e:
                print(f"文件 {file} 加载失败: {e}")
                continue

            for d in docs:
                d.metadata["filename"] = file
            documents.extend(docs)
        
        return documents

    def _build_index(self):
        """构建索引"""
        # 加载文档
        documents = self._load_documents()

        # 文本切分
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        docs = []
        for doc in tqdm(documents, desc="Splitting documents"):
            docs.extend(text_splitter.split_documents([doc]))

        # 创建FAISS向量库
        vectorstore = FAISS.from_documents(docs, self.embeddings)
        
        # 确保目录存在
        os.makedirs(self.index_path, exist_ok=True)
        vectorstore.save_local(self.index_path)
        
        # 保存元数据
        current_hash = self._calculate_folder_hash(self.folder_path)
        self._save_index_metadata(current_hash)

    def _load_documents_for_bm25(self):
        """为BM25加载文档"""
        documents = self._load_documents()

        # 文本切分
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        self.docs = []
        for doc in documents:
            self.docs.extend(text_splitter.split_documents([doc]))

    def query(self, query: str):
        """查询方法"""
        compressed_docs = self.compression_retriever.invoke(query)
        return [(doc.page_content, doc.metadata) for doc in compressed_docs]


def main():
    # 从配置文件获取 RAG 配置
    rag_config = get_rag_config()
    
    retriever = Retriever(
        folder_path=rag_config['folder_path'],
        embedding_model=rag_config['embedding_model'],
        rerank_model=rag_config['rerank_model'],
        index_path=rag_config['index_path'],
        bm25_k=rag_config['bm25_k'],
        faiss_k=rag_config['faiss_k'],
        top_n=rag_config['top_n'],
        chunk_size=rag_config['chunk_size'],
        chunk_overlap=rag_config['chunk_overlap'],
        device=rag_config['device']
    )

    query_text = "速诺的用法是什么样子的"
    results = retriever.query(query_text)

    print(f"\n查询: {query_text}\n{'='*60}\n")
    for i, (text, meta) in enumerate(results, 1):
        filename = meta.get('filename', 'unknown')
        source = meta.get('source', 'N/A')
        print(f"Result {i}")
        print(f"  File: {filename}")
        print(f"  Source: {source}")
        print(f"  Content:\n{text}\n{'-'*60}\n")


if __name__ == "__main__":
    main()
