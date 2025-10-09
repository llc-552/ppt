import asyncio
from langgraph.graph import StateGraph, START
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import interrupt
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from main.prompt import vet_chat_prompt
from main.rag import Retriever
from main.chatstore import ChatStore
from main.config import get_openai_config, get_redis_config, get_rag_config, get_vetchat_config

class VetChat:
    def __init__(self, user_id: str, conv_id: str = None, redis_host=None, redis_port=None, rag: bool = False):
        self.user_id = user_id
        self.conv_id = conv_id  # 临时设置，在异步初始化中处理
        self.rag = rag
        # 从配置文件获取 Redis 配置
        redis_config = get_redis_config()
        actual_redis_host = redis_host if redis_host is not None else redis_config['host']
        actual_redis_port = redis_port if redis_port is not None else redis_config['port']
        # 初始化聊天存储
        self.chat_store = ChatStore(host=actual_redis_host, port=actual_redis_port)
        self._initialized = False

    async def _ensure_initialized(self):
        """确保异步初始化完成"""
        if not self._initialized:
            # 如果没有提供conv_id，创建新会话
            if self.conv_id is None:
                self.conv_id = await self.chat_store.create_new_conversation(self.user_id)
            self._initialized = True

        # 初始化内存
        self.memory = InMemorySaver()

        # 从配置文件获取 OpenAI 配置
        openai_config = get_openai_config()
        # 初始化 LLM
        self.model = ChatOpenAI(
            openai_api_base=openai_config['api_base'],
            openai_api_key=openai_config['api_key'],
            model=openai_config['model'],
            temperature=openai_config['temperature'],
        )

        # 只在启用RAG时初始化检索器
        if self.rag:
            print(f"🔍 [VetChat] RAG已启用，正在初始化检索器...")
            # 从配置文件获取 RAG 配置
            rag_config = get_rag_config()
            self.retriever = Retriever(
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
            print(f"✅ [VetChat] RAG检索器初始化完成")
        else:
            self.retriever = None
            print(f"⚠️ [VetChat] RAG未启用，跳过检索器初始化")

        #初始化摘要节点
        vetchat_config = get_vetchat_config()
        self.summarization_node = SummarizationNode(
            token_counter=count_tokens_approximately,
            model=self.model,
            max_tokens=vetchat_config['max_tokens'],
            max_summary_tokens=vetchat_config['max_summary_tokens'],
            output_messages_key="llm_input_messages",
        )

        # 初始化状态
        self.state = {
            "user_id": self.user_id,
            "conv_id": self.conv_id,
            "show_history": False,
            "show_state": False,
            "vetchat": {"conversation": [], "count": 0},
            "current_output": [],
            "end": False,
            "rag": self.rag,
            "latest_user_input": "",
        }

        # 初始化 StateGraph
        self.graph = StateGraph(dict, debug=True)
        self.graph.add_node("user", self.user_node)
        self.graph.add_node("vet_chatbot", self.vet_node)
        self.graph.add_node("end", self.end_node)
        
        self.graph.add_edge(START, "user")
        self.graph.add_edge("user", "vet_chatbot")
        self.graph.add_edge("vet_chatbot", "user")

        # **编译图，优化性能**
        self.compiled_graph = self.graph.compile()

        # 初始化 agent
        self.vet_chatbot_agent = create_react_agent(
            model=self.model,
            tools=[],
            pre_model_hook=self.pre_model_hook,
            prompt=vet_chat_prompt,
            checkpointer=self.memory,
        )

    # =========================
    # 会话管理方法
    # =========================
    async def get_user_conversations(self):
        """获取用户的所有会话"""
        await self._ensure_initialized()
        return await self.chat_store.get_user_conversations(self.user_id)
    
    async def create_new_conversation(self, title: str = None):
        """创建新会话"""
        await self._ensure_initialized()
        return await self.chat_store.create_new_conversation(self.user_id, title)
    
    def switch_conversation(self, conv_id: str):
        """切换到指定会话"""
        self.conv_id = conv_id
        
    async def delete_current_conversation(self):
        """删除当前会话"""
        await self._ensure_initialized()
        return await self.chat_store.delete_conversation(self.user_id, self.conv_id)
    
    async def clear_current_conversation(self):
        """清空当前会话"""
        await self._ensure_initialized()
        return await self.chat_store.clear_conversation(self.user_id, self.conv_id)

    # =========================
    # 用户输入节点
    # =========================
    async def user_node(self, state: dict) -> dict:
        if not state.get("latest_user_input"):
            interrupt("请患者输入症状或问题：")
            return state
            
        user_info = state["user_id"] + " " + state["conv_id"]
        user_input = state.pop("latest_user_input")
        print(f"👍 [User]{user_info} 输入: {user_input}")

        human_msg = HumanMessage(content=user_input)
        state["vetchat"]["conversation"].append(human_msg)
        
        # 保存到聊天存储
        await self.chat_store.add_message(self.user_id, self.conv_id, human_msg)
        return state

    # =========================
    # 兽医对话节点
    # =========================
    async def vet_node(self, state: dict) -> dict:
        user_info = state["user_id"] + " " + state["conv_id"]
        print(f"当前节点[{user_info}]:vet_chatbot")

        # 确保初始化完成
        await self._ensure_initialized()
        
        # 从聊天存储加载历史消息
        messages = await self.chat_store.get_messages(self.user_id, self.conv_id)

        config = {"configurable": {"thread_id": state["conv_id"]}}

        #读取最新的用户输入进行RAG
        lastest_user_input = state["vetchat"]["conversation"][-1].content

        #RAG模块
        if state["rag"] and self.retriever is not None:
            rag_results = self.retriever.query(lastest_user_input)
            # 格式化RAG结果
            formatted_rag_results = ""
            if rag_results:  # 修复逻辑错误：应该是if rag_results而不是if not rag_results
                rag_content_list = []
                for text, meta in rag_results:
                    filename = meta.get('filename', '未知文件')
                    source = meta.get('source', '未知来源')
                    rag_content_list.append(f"来源：{filename}\n内容：{text}")
                
                formatted_rag_results = f"\n\n以下是一些参考材料：\n{chr(10).join(rag_content_list)}\n"
            
            # 将RAG结果添加到消息中
            enhanced_messages = messages.copy()
            if formatted_rag_results and len(enhanced_messages) > 0:
                # 在最新的用户消息后添加RAG结果
                last_user_msg = enhanced_messages[-1]
                if hasattr(last_user_msg, 'content'):
                    enhanced_content = last_user_msg.content + formatted_rag_results
                    # 创建新的消息对象，保持原有类型
                    enhanced_messages[-1] = HumanMessage(content=enhanced_content)
            
            #打印一下结果
            if True:
                print("RAG 查询结果:")
                for text, meta in rag_results:
                    print(f"文件名: {meta['filename']}")
                    print(f"来源: {meta['source']}")
                    print(f"内容: {text}")
                    print("-"*60)
            
                print(f"历史记录有什么: {messages}")
                print("#"*60)
                if not enhanced_messages:
                    print(f"增强后的历史记录有什么: {enhanced_messages[-1]}")

            response = await self.vet_chatbot_agent.ainvoke({"messages": enhanced_messages}, config=config)
        else:
            response = await self.vet_chatbot_agent.ainvoke({"messages": messages}, config=config)
        
        ai_msg = AIMessage(content=response["messages"][-1].content)
        print("[Vet AI 回复]", ai_msg.content)

        state["vetchat"]["conversation"].append(ai_msg)
        state["current_output"] = ai_msg.content

        # 保存到聊天存储
        await self.chat_store.add_message(self.user_id, self.conv_id, ai_msg)
        
        if state["show_history"]:
            # 显示历史记录
            history_messages = await self.chat_store.get_messages(self.user_id, self.conv_id)
            for msg in history_messages:
                msg_type = "User" if isinstance(msg, HumanMessage) else "AI"
                print(f"[{msg_type}]: {msg.content}")
                
        if state["show_state"]:
            print(f"查看 state:\n{state}")
        
        return state

    # =========================
    # 结束节点
    # =========================
    @staticmethod
    def end_node(state: dict) -> dict:
        state["end"] = True
        return state

    # =========================
    # 模型输入预处理
    # =========================
    @staticmethod
    def pre_model_hook(state):
        vetchat_config = get_vetchat_config()
        trimmed_messages = trim_messages(
            state["messages"],
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=vetchat_config['trim_max_tokens'],
            start_on="human",
            end_on=("human", "tool"),
        )
        return {"llm_input_messages": trimmed_messages}

    # =========================
    # 设置用户输入
    # =========================
    async def set_user_input(self, text: str):
        await self._ensure_initialized()
        self.state["latest_user_input"] = text

    # =========================
    # 运行对话（流式）
    # =========================
    async def run(self):
        """使用流式模式运行对话"""
        try:
            await self._ensure_initialized()
            
            # 使用 stream_mode="updates" 来获取每个节点的更新
            async for chunk in self.compiled_graph.astream(
                self.state, 
                stream_mode="updates"
            ):
                print(f"📦 流式输出: {chunk}")
                
                # 检查是否遇到中断
                if "__interrupt__" in chunk:
                    interrupt_info = chunk["__interrupt__"]
                    print(f"⏸️  遇到中断: {interrupt_info}")
                    print("提示：需要用户输入才能继续")
                    return
                
                # 处理每个节点的更新
                for node_name, node_state in chunk.items():
                    print(f"\n🔄 节点 [{node_name}] 更新:")
                    
                    # 只有当 node_state 是字典时才处理
                    if isinstance(node_state, dict):
                        # 如果是兽医回复，进行流式打印
                        if node_name == "vet_chatbot" and node_state.get("current_output"):
                            print(f"🤖 [Vet AI]: {node_state['current_output']}")
                        
                        # 更新本地状态
                        self.state.update(node_state)
                        
                        # 检查是否结束
                        if node_state.get("end"):
                            print("✅ 对话结束")
                            return
                        
        except Exception as e:
            print(f"❌ 运行时错误: {e}")
            raise
