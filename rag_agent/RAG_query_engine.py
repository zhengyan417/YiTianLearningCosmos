import logging
import os
import sys
from typing import List

import torch
from dotenv import load_dotenv
from llama_index.core import Settings, StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore

load_dotenv()


def get_device() -> str:
    return "cuda:0" if torch.cuda.is_available() else "cpu"


class RAGQueryEngine:
    def __init__(
        self,
        embed_model_path: str,
        storage_dir: str,
        similarity_top_k: int = 3,
        with_mmr: bool = False,
        mmr_threshold: float = 0.5,
        device: str = None,
    ):
        """
        RAG 检索引擎（仅负责向量检索，不加载本地 LLM）

        向量检索使用本地嵌入模型（HuggingFace），最终文本生成由
        外部 LLM（DashScope Qwen-max）负责，两者完全解耦。

        Args:
            embed_model_path: 本地嵌入模型路径（如 bge-base-zh-v1.5）
            storage_dir: FAISS 向量索引存储目录
            similarity_top_k: 检索 top-k 文档片段
            with_mmr: 是否启用 MMR 多样性排序
            mmr_threshold: MMR 阈值
            device: 运行设备，默认自动检测（cuda:0 / cpu）
        """
        self.embed_model_path = embed_model_path
        self.storage_dir = storage_dir
        self.similarity_top_k = similarity_top_k
        self.with_mmr = with_mmr
        self.mmr_threshold = mmr_threshold
        self.device = device or get_device()

        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self._setup_embedding()
        self._load_index()

    def _setup_embedding(self):
        """加载本地嵌入模型"""
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=self.embed_model_path,
            device=self.device,
        )
        self.logger.info(f"嵌入模型加载完成：{self.embed_model_path}（设备：{self.device}）")

    def _load_index(self):
        """从磁盘加载 FAISS 向量索引并初始化检索器"""
        vector_store = FaissVectorStore.from_persist_dir(self.storage_dir)
        storage_context = StorageContext.from_defaults(
            persist_dir=self.storage_dir,
            vector_store=vector_store,
        )
        self.index = load_index_from_storage(storage_context)
        self.retriever = self.index.as_retriever(
            similarity_top_k=self.similarity_top_k,
            mmr=self.with_mmr,
            mmr_threshold=self.mmr_threshold,
        )
        self.logger.info("FAISS 索引与检索器初始化完成")

    def query_with_contexts(self, question: str) -> List[str]:
        """
        检索与问题相关的上下文片段，不调用任何 LLM。

        Returns:
            检索到的文本片段列表，由调用方传给外部 LLM 生成回答。
        """
        nodes = self.retriever.retrieve(question)
        return [node.get_content() for node in nodes]


if __name__ == "__main__":
    engine = RAGQueryEngine(
        embed_model_path=os.getenv("EMBED_PATH"),
        storage_dir=os.getenv("STORAGE_DIR", "./storage"),
        similarity_top_k=3,
        with_mmr=True,
        mmr_threshold=0.5,
    )

    question = "我出现了眩晕，胸闷，咯吐痰多，犯困、嗜睡，形体丰满或肥胖，舌质淡胖的症状，可能是什么情况?"
    contexts = engine.query_with_contexts(question)
    for i, ctx in enumerate(contexts, 1):
        print(f"--- 上下文 {i} ---\n{ctx[:300]}\n")
