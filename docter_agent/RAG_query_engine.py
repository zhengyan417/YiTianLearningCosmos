# rag_query_engine.py
import logging
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
import torch
from typing import List, Iterator, Tuple, Union
from llama_index.core import Settings, StorageContext, load_index_from_storage, PromptTemplate
from llama_index.core.indices.query.query_transform.base import HyDEQueryTransform
from llama_index.core.query_engine import TransformQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.postprocessor import LLMRerank
from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.response_synthesizers import get_response_synthesizer
from transformers import AutoTokenizer, BitsAndBytesConfig
# from llama_index.llms.dashscope import DashScope, DashScopeGenerationModels

import dotenv
dotenv.load_dotenv()

QA_TEMPLATE = PromptTemplate(
    "你是一个专业的中医助手。请根据以下上下文信息回答用户的问题。\n"
    "上下文信息：\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "请仅基于以上信息，用简洁的语言回答问题，不要进行过度分析或重复：\n"
    "问题: {query_str}\n"
    "回答: "
)

def get_device():
    if torch.cuda.is_available():
        return "cuda:0"
    else:
        return "cpu"

class RAGQueryEngine:
    def __init__(
        self,
        llm_model_path: str,
        embed_model_path: str,
        storage_dir: str,
        context_window: int = 8192,
        max_new_tokens: int = 1024,
        similarity_top_k: int = 3,
        streaming: bool = False,
        device: str = None,
        with_rerank: bool = False,
        reranker_top_n: int = 3,
        with_mmr: bool = False,
        mmr_threshold: float = 0.5,
        with_query_transform: bool = False,
    ):
        """
        初始化 RAG 查询引擎
        
        Args:
            llm_model_path: 本地大语言模型路径
            embed_model_path: 本地嵌入模型路径
            storage_dir: 向量索引存储目录
            context_window: LLM 上下文窗口
            max_new_tokens: 最大生成 token 数
            similarity_top_k: 检索 top-k 文档
            streaming: 是否启用流式输出
            device: 运行设备（如 'cuda:0', 'cpu'）
            with_rerank: 是否启用重排序,
            reranker_top_n: 重排序 top-n 文档
            with_mmr: 是否启用 MMR,
            mmr_threshold: MMR 阈值
        """
        self.llm_model_path = llm_model_path
        self.embed_model_path = embed_model_path
        self.storage_dir = storage_dir
        self.similarity_top_k = similarity_top_k
        self.streaming = streaming
        self.with_rerank = with_rerank
        self.reranker_top_n = reranker_top_n
        self.with_mmr = with_mmr
        self.mmr_threshold = mmr_threshold
        self.with_query_transform = with_query_transform

        if device is None:
            self.device = get_device()
        else:
            self.device = device
        
        # 配置日志
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # 初始化组件
        self._setup_models(context_window, max_new_tokens)
        self._load_index()

    def _setup_models(self, context_window: int, max_new_tokens: int):
        """加载 LLM 和 Embedding 模型"""
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

        tokenizer = AutoTokenizer.from_pretrained(
            self.llm_model_path,
            trust_remote_code=True,
            padding_side="left"  # Qwen 推荐
        )

        Settings.llm = HuggingFaceLLM(
            context_window=context_window,
            max_new_tokens=max_new_tokens,
            generate_kwargs={
                "temperature": 0.7,
                "do_sample": True,
                "top_p": 0.8,
                "top_k": 20,
                "repetition_penalty": 1.5,
            },
            tokenizer=tokenizer,
            model_name=self.llm_model_path,
            device_map=self.device,
            model_kwargs={
                "trust_remote_code": True,
                "quantization_config": quantization_config,
            },
        )

        Settings.embed_model = HuggingFaceEmbedding(model_name=self.embed_model_path)

        self.logger.info("==========模型加载完成===========")

    def _load_index(self):
        """从磁盘加载向量索引"""

        vector_store = FaissVectorStore.from_persist_dir(self.storage_dir)
        storage_context = StorageContext.from_defaults(
            persist_dir=self.storage_dir,
            vector_store=vector_store
        )
        self.index = load_index_from_storage(storage_context)
        
        self.logger.info("=========索引加载完成===========")

        # 基础查询引擎
        retriever = self.index.as_retriever(
            similarity_top_k=self.similarity_top_k,  # 增加检索数量
            mmr=self.with_mmr,            # 启用MMR
            mmr_threshold=self.mmr_threshold,    # MMR阈值
        )
        response_synthesizer = get_response_synthesizer(
            streaming=self.streaming,
            llm=Settings.llm,
            # text_qa_template=QA_TEMPLATE,
        )
        query_engine = RetrieverQueryEngine(
            retriever = retriever,
            response_synthesizer = response_synthesizer,
            node_postprocessors = [LLMRerank(top_n=self.reranker_top_n)] if self.with_rerank else None,
        )

        # 应用 HyDE 查询转换
        # hyde = HyDEQueryTransform(include_original=True)
        # self.query_engine = TransformQueryEngine(query_engine, query_transform=hyde)
        self.query_engine = query_engine
        
        self.logger.info("=========查询引擎初始化完成===========")
    
    
    def query_with_contexts(self, question: str) -> Tuple[str, List[str]]:
        # 获取底层 response object
        response = self.query_engine.query(question)

        # 提取检索到的节点（即上下文）
        retrieved_nodes = response.source_nodes if hasattr(response, 'source_nodes') else []
        contexts = [node.get_content() for node in retrieved_nodes]

        return contexts
    
    def query(self, question: str) -> Union[str, Iterator[str]]:
        """
        执行 RAG 查询
        
        Args:
            question: 用户问题
            
        Returns:
            若 streaming=True: 返回 token 生成器（Iterator[str]）
            否则: 返回完整回答字符串（str）
        """
        
        # 查询改写
        if self.with_query_transform:
            self.logger.info("========执行查询改写========")
            print(f"输入问题:{question}\n")
            question = self.rewrite_query_simple(question, Settings.llm)
            print(f"改写问题:{question}\n")
        self.logger.info("========向量数据库开始查询========")
        response = self.query_engine.query(question)

        self.logger.info("========模型开始输出========")
        if self.streaming:
            return self._stream_response(response)
        else:
            return str(response)

    def _stream_response(self, response) -> Iterator[str]:
        """流式输出生成器"""
        for token in response.response_gen:
            yield token

    def rewrite_query_simple(self, question: str, llm) -> str:
        prompt = f"""你是一个中医助手，请将以下口语化问题改写为规范、简洁的中医辨证问诊语句，不要添加额外信息，不要回答问题：

    原始问题：{question}

    改写后："""
        response = llm.complete(prompt, max_tokens=64, temperature=0.1)
        return str(response).strip()

if __name__ == "__main__":
    # 配置路径
    LLM_PATH = os.getenv("LLM_PATH")
    EMBED_PATH = os.getenv("EMBED_PATH")
    STORAGE_DIR = os.getenv("STORAGE_DIR")

    # 创建引擎
    engine = RAGQueryEngine(
        llm_model_path=LLM_PATH,
        embed_model_path=EMBED_PATH,
        storage_dir=STORAGE_DIR,
        streaming=True,
        similarity_top_k=3,
        with_rerank=False, # 重排序
        with_mmr=True, # MMR
        mmr_threshold=0.5,
        with_query_transform=False, # 查询改写
    )

    # 执行查询
    question = "我出现了眩晕，胸闷，咯吐痰多，痰易咯吐，犯困、嗜睡，形体丰满或肥胖，肢体麻木，舌质淡胖的症状,可能是什么情况?"

    response_stream = engine.query(question)
    for token in response_stream:
        print(token, end="", flush=True)
    print()  # 换行