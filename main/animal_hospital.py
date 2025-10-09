import asyncio
import redis
import json
from langgraph.graph import StateGraph, START
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from main.prompt import reception_prompt, router_prompt, internal_medicine_prompt, summary_prompt, internal_medicine_diagnosis_prompt
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.types import interrupt
from main.config import get_openai_config, get_redis_config


class AnimalHospital:
    def __init__(self, user_id: str, conv_id: str, redis_host=None, redis_port=None):
        self.user_id = user_id
        self.conv_id = conv_id
        
        # 从配置文件获取 Redis 配置
        redis_config = get_redis_config()
        actual_redis_host = redis_host if redis_host is not None else redis_config['host']
        actual_redis_port = redis_port if redis_port is not None else redis_config['port']
        
        # Redis 客户端 - 添加连接测试
        try:
            self.r = redis.Redis(host=actual_redis_host, port=actual_redis_port, decode_responses=True)
            self.r.ping()  # 测试连接
        except redis.ConnectionError:
            print("⚠️ Redis连接失败，将使用内存存储")
            self.r = None
        
        # 问诊轮次
        self.reception_rounds = 3
        self.doctor_rounds = 3
        
        # checkpointer 用于保存每个 agent 状态
        self.reception_checkpointer = InMemorySaver()
        self.internal_checkpointer = InMemorySaver()
        
        # 从配置文件获取 OpenAI 配置
        openai_config = get_openai_config()
        # 初始化 LLM
        self.model = ChatOpenAI(
            openai_api_base=openai_config['api_base'],
            openai_api_key=openai_config['api_key'],
            model=openai_config['model'],
            temperature=openai_config['temperature'],
        )
        
        # 创建 agents
        self.reception_agent = create_react_agent(model=self.model, tools=[], prompt=reception_prompt, checkpointer=self.reception_checkpointer)
        self.router_agent = create_react_agent(model=self.model, tools=[], prompt=router_prompt)
        self.diagnosis_agent = create_react_agent(model=self.model, tools=[], prompt=internal_medicine_diagnosis_prompt)
        self.summary_agent = create_react_agent(model=self.model, tools=[], prompt=summary_prompt)
        self.internal_medicine_agent = create_react_agent(model=self.model, tools=[], prompt=internal_medicine_prompt)
        
        # 初始化状态
        self.state = {
            "user_id": user_id,
            "conv_id": conv_id,
            "reception_state": {"conversation": [], "count": 0},
            "doctor_state": {"conversation": [], "count": 0},
            "node_state": {"reception": False, "doctor": False, "router": False, "summary": False, "diagnosis": False, "greet": False, "patient": False, "chat": False},
            "human_count": 0,
            "current_output": [],
            "animal_info": "",
            "next_department": None,
            "end": False,
            "latest_user_input": "",
        }
        
        # 初始化 StateGraph
        self.graph = StateGraph(dict, debug=True)
        self.graph.add_node("greet", self.greet)
        self.graph.add_node("reception", self.reception)
        self.graph.add_node("end", self.end)
        self.graph.add_node("summary", self.summary)
        self.graph.add_node("rp", self.rp)
        self.graph.add_node("dp", self.dp)
        self.graph.add_node("router", self.router)
        self.graph.add_node("doctor", self.doctor)
        self.graph.add_node("diagnosis", self.diagnosis)
        self.graph.add_node("patient", self.patient)
        self.graph.add_node("chat", self.chat)
        
        # 添加边
        self.graph.add_edge(START, "greet")
        self.graph.add_edge("greet", "rp")
        self.graph.add_edge("rp", "reception")
        self.graph.add_conditional_edges("reception", self.should_continue_reception, {"rp": "rp", "router": "router"})
        self.graph.add_edge("router", "summary")
        self.graph.add_edge("summary", "doctor")
        self.graph.add_conditional_edges("doctor", self.should_continue_patient, {"dp": "dp", "diagnosis": "diagnosis"})
        self.graph.add_edge("dp", "doctor")
        self.graph.add_edge("diagnosis", "patient")
        self.graph.add_edge("patient", "chat")
        self.graph.add_edge("chat", "patient")  # 添加循环边，允许持续对话
        
        # **编译图，优化性能**
        self.compiled_graph = self.graph.compile()
    
    # =========================
    # Redis key
    # =========================
    def redis_key(self) -> str:
        return f"hospital:{self.user_id}:{self.conv_id}"
    
    # =========================
    # 序列化/反序列化消息
    # =========================
    @staticmethod
    def serialize_msg(msg):
        if isinstance(msg, HumanMessage):
            return json.dumps({"type": "human", "content": msg.content})
        elif isinstance(msg, AIMessage):
            return json.dumps({"type": "ai", "content": msg.content})
        elif isinstance(msg, SystemMessage):
            return json.dumps({"type": "system", "content": msg.content})
        else:
            raise ValueError("未知消息类型")
    
    @staticmethod
    def deserialize_msg(msg_json):
        data = json.loads(msg_json)
        msg_type = data.get("type", "")
        if msg_type == "human":
            return HumanMessage(content=data["content"])
        elif msg_type == "ai":
            return AIMessage(content=data["content"])
        elif msg_type == "system":
            return SystemMessage(content=data["content"])
        else:
            raise ValueError("未知消息类型")
    
    # =========================
    # 辅助函数
    # =========================
    def add_message(self, msg, conversation_list):
        conversation_list.append(msg)
        
        # 保存到Redis（如果可用）
        if self.r is not None:
            try:
                self.r.rpush(self.redis_key(), self.serialize_msg(msg))
            except redis.ConnectionError:
                print("⚠️ Redis写入失败")
    
    def load_history_from_redis(self) -> list:
        if self.r is None:
            return []
        try:
            msgs_json = self.r.lrange(self.redis_key(), 0, -1)
            return [self.deserialize_msg(msg_json) for msg_json in msgs_json]
        except redis.ConnectionError:
            print("⚠️ Redis读取失败")
            return []
    
    # =========================
    # 设置用户输入
    # =========================
    def set_user_input(self, text: str):
        self.state["latest_user_input"] = text
    
    # =========================
    # 节点函数
    # =========================
    def greet(self, state: dict):
        if state["node_state"]["greet"] == True:
            return state
        user_info = f"{state['user_id']}:{state['conv_id']}"
        print(f"[Greet-{user_info}]您好，欢迎来到agent animal hospital！")
        # greet是内部节点，使用system_message而不是current_output
        state['system_message'] = "您好，欢迎来到agent animal hospital！"
        state["node_state"]["greet"] = True
        return state
    
    async def rp(self, state: dict) -> dict:
        """患者输入节点，每次运行都等待新的用户输入"""
        if state["node_state"]["reception"]:
            return state
        
        if "latest_user_input" not in state or not state["latest_user_input"]:
            interrupt("请患者输入症状或问题：")
            return state  
        
        user_input = state.pop("latest_user_input")
        user_info = f"{state['user_id']}:{state['conv_id']}"
        print(f"👍[rp-{user_info}] 用户输入: {user_input}")
        
        # 根据状态选择挂号对话还是医生对话
        target_conversation = state['reception_state']['conversation']
        human_msg = HumanMessage(content=user_input)
        self.add_message(human_msg, target_conversation)
        state['reception_state']['count'] += 1
        if state['reception_state']['count'] >= self.reception_rounds:
            state["node_state"]["reception"] = True
        
        return state
    
    async def dp(self, state: dict) -> dict:
        """患者输入节点，每次运行都等待新的用户输入"""
        if state["node_state"]["doctor"]:
            print(f"⚠️ dp 节点被跳过（医生问诊已完成）")
            return state 
        user_info = f"{state['user_id']}:{state['conv_id']}"
        
        print(f"🟢 [进入 dp 节点] count={state['doctor_state']['count']}, latest_user_input={'存在' if state.get('latest_user_input') else '不存在'}")
        
        if "latest_user_input" not in state or not state["latest_user_input"]:
            print(f"⏸️ [dp] 没有用户输入，触发 interrupt")
            interrupt("请患者输入症状或问题：")
            return state  
        
        user_input = state.pop("latest_user_input")
        print(f"👍[dp-{user_info}] 用户输入: {user_input}")
        
        target_conversation = state['doctor_state']['conversation']
        human_msg = HumanMessage(content=user_input)
        self.add_message(human_msg, target_conversation)
        
        # dp 接收用户输入后增加 count
        old_count = state['doctor_state']['count']
        state['doctor_state']['count'] += 1
        new_count = state['doctor_state']['count']
        print(f"📊 [dp] count 更新: {old_count} -> {new_count}")
        
        if state['doctor_state']['count'] >= self.doctor_rounds:
            state["node_state"]["doctor"] = True
            print(f"✅ [dp] 达到问诊轮次，设置 doctor 完成标志")
        
        return state
    
    async def reception(self, state: dict) -> dict:
        if state["node_state"]["reception"]:
            return state
        
        user_info = f"{state['user_id']}:{state['conv_id']}"
        history_chat = state['reception_state']['conversation']
        # 调用 agent，传入完整历史
        print(f"[reception-{user_info}] 当前对话历史:")
        print(history_chat)
        response = await self.reception_agent.ainvoke({"messages": history_chat})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[reception-{user_info} AI回复]", ai_msg.content)

        self.add_message(ai_msg, history_chat)
        state["current_output"] = ai_msg.content
        return state
    
    async def router(self, state: dict) -> dict:
        if state["node_state"]["router"]:
            return state
        
        user_info = f"{state['user_id']}:{state['conv_id']}"
        history_chat = state['reception_state']['conversation']
        
        # 调用 agent，传入完整历史
        response = await self.router_agent.ainvoke({"messages": history_chat})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[router \n -{user_info} AI回复]", ai_msg.content)
        self.add_message(ai_msg, history_chat)

        state["next_department"] = ai_msg.content
        state["node_state"]["router"] = True
        # 清空 current_output，避免保留上一个节点的输出
        state["current_output"] = ""
        return state
    
    async def summary(self, state: dict) -> dict:
        if state["node_state"]["summary"]:
            return state
        
        user_info = f"{state['user_id']}:{state['conv_id']}"
        history_chat = state['reception_state']['conversation']
        
        # 调用 agent，传入完整历史
        response = await self.summary_agent.ainvoke({"messages": history_chat})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[summary \n-{user_info} AI回复]", ai_msg.content)
        self.add_message(ai_msg, history_chat)
        state["animal_info"] = ai_msg.content
        state["node_state"]["summary"] = True
        # 清空 current_output，避免保留上一个节点的输出
        state["current_output"] = ""
        return state
    
    async def doctor(self, state: dict) -> dict:
        if state["node_state"]["doctor"]:
            print(f"⚠️ doctor 节点被跳过（已完成）")
            return state
        
        user_info = f"{state['user_id']}:{state['conv_id']}"
        current_count = state['doctor_state']['count']
        print(f"🔵 [进入 doctor 节点] count={current_count}, 对话历史长度={len(state['doctor_state']['conversation'])}")
        
        history_chat = state['doctor_state']['conversation']
        animal_info = state.get("animal_info", "")
        system_msg = SystemMessage(content=f"以下是宠物的基本信息：\n{animal_info}")
        messages = [system_msg] + history_chat
        
        
        response = await self.internal_medicine_agent.ainvoke({"messages": messages})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[doctor \n-{user_info} AI回复]", ai_msg.content)
        self.add_message(ai_msg, history_chat)
        state["current_output"] = ai_msg.content
        
        return state
    
    async def diagnosis(self, state: dict) -> dict:
        if state["node_state"]["diagnosis"]:
            return state
        
        user_info = f"{state['user_id']}:{state['conv_id']}"
        history_chat = state['doctor_state']['conversation']
        # 调用 agent，传入完整历史
        animal_info = state.get("animal_info", "")
        system_msg = SystemMessage(content=f"以下是宠物的基本信息：\n{animal_info}")
        messages = [system_msg] + history_chat
        
        response = await self.diagnosis_agent.ainvoke({"messages": messages})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[diagnosis-{user_info} AI回复]", ai_msg.content)
        self.add_message(ai_msg, history_chat)
        state["current_output"] = ai_msg.content
        state["diagnosis"] = ai_msg.content
        
        state["node_state"]["diagnosis"] = True
        return state

    async def patient(self, state: dict) -> dict:
        """患者输入节点，每次运行都等待新的用户输入"""
        user_info = f"{state['user_id']}:{state['conv_id']}"
        
        if "latest_user_input" not in state or not state["latest_user_input"]:
            print(f"⏸️ [patient] 没有用户输入，触发 interrupt")
            interrupt("请患者继续描述症状或提问：")
            return state  
        
        user_input = state.pop("latest_user_input")
        print(f"👍[patient-{user_info}] 用户输入: {user_input}")
        
        # 将用户输入添加到医生对话历史中
        target_conversation = state['doctor_state']['conversation']
        human_msg = HumanMessage(content=user_input)
        self.add_message(human_msg, target_conversation)
        
        # 设置patient节点完成状态
        state["node_state"]["patient"] = True
        print(f"✅ [patient] 用户输入已处理，设置完成标志")
        
        return state

    async def chat(self, state: dict) -> dict:
        """持续聊天节点，处理诊断后的后续交流"""
        user_info = f"{state['user_id']}:{state['conv_id']}"
        print(f"🔵 [进入 chat 节点] 开始后续交流")
        
        history_chat = state['doctor_state']['conversation']
        animal_info = state.get("animal_info", "")
        system_msg = SystemMessage(content=f"以下是宠物的基本信息：\n{animal_info}")
        messages = [system_msg] + history_chat
        
        response = await self.internal_medicine_agent.ainvoke({"messages": messages})
        ai_msg = AIMessage(content=response["messages"][-1].content)
        
        print(f"[Chat-{user_info} AI回复]", ai_msg.content)
        self.add_message(ai_msg, history_chat)
        state["current_output"] = ai_msg.content
        
        # 重置patient节点状态，允许继续接收用户输入
        state["node_state"]["patient"] = False
        print(f"🔄 [chat] 重置patient状态，准备接收下一轮用户输入")
        
        return state


    def end(self, state: dict) -> dict:
        user_info = f"{state['user_id']}:{state['conv_id']}"
        print(f"[end-{user_info}] 就诊结束")
        state['system_message'] = "[System]: 就诊结束"
        state["end"] = True
        return state
    
    # =========================
    # 条件函数
    # =========================
    def should_continue_reception(self, state: dict) -> str:
        return "rp" if state['reception_state']['count'] < self.reception_rounds else "router"
    
    def should_continue_patient(self, state: dict) -> str:
        """ 判断病人是否完成轮次，完成后直接进入诊断 """
        return "dp" if state['doctor_state']['count'] < self.doctor_rounds else "diagnosis"
    
    # =========================
    # 运行对话（流式）
    # =========================
    async def run(self):
        try:
            while not self.state["end"]:
                async for event in self.compiled_graph.astream(self.state):
                    if "__end__" in event:
                        self.state = event["__end__"]
                    if "__interrupt__" in event:
                        break
                    if self.state.get("current_output"):
                        user_info = f"{self.state['user_id']}:{self.state['conv_id']}"
                        print(f"[Hospital-{user_info}]:", self.state["current_output"])
                await asyncio.sleep(0.1)  # 防止阻塞
        except Exception as e:
            print(f"运行时错误: {e}")
            raise