from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncio
import uuid
import json
from typing import Optional, Dict
from main.animal_hospital import AnimalHospital
from main.vet import VetChat  # 使用新的 VetChat 类
from main.config import get_redis_config

# -------------------------------
# 初始化 FastAPI
# -------------------------------
app = FastAPI()

# 使用相对路径或从项目根目录开始的路径
import os
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(base_dir, "main", "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "main", "static")), name="static")

state_lock = asyncio.Lock()

# -------------------------------
# 全局状态管理
# -------------------------------
animal_hospital_instances: Dict[str, AnimalHospital] = {}  # 存储多个 AnimalHospital 实例
vet_chat_instances: Dict[str, VetChat] = {}  # 存储多个 VetChat 实例

# -------------------------------
# 启动事件
# -------------------------------
@app.on_event("startup")
async def startup_event():
    print("✅ AnimalHospital 服务已准备就绪")
    print("✅ VetChat 服务已准备就绪")

# -------------------------------
# 辅助函数
# -------------------------------
def get_or_create_vet_chat(user_id: Optional[str] = None, task_id: Optional[str] = None, rag_enabled: bool = False) -> VetChat:
    """获取或创建 VetChat 实例"""
    # 用户ID由用户输入，如果没有则使用默认值
    actual_user_id = user_id or "anonymous_user"
    
    # 对话ID随机生成（如果task_id存在则使用，否则生成新的）
    if task_id:
        actual_conv_id = task_id
    else:
        actual_conv_id = f"conv_{uuid.uuid4().hex[:8]}"
    
    # 使用 user_id + conv_id 作为实例的唯一键
    instance_key = f"{actual_user_id}:{actual_conv_id}"
    
    #实例化VetChat
    if instance_key not in vet_chat_instances:
        vet_chat_instances[instance_key] = VetChat(
            user_id=actual_user_id, 
            conv_id=actual_conv_id,
            rag=rag_enabled
        )
        print(f"✅ 创建新的 VetChat 实例: user_id={actual_user_id}, conv_id={actual_conv_id}, rag={rag_enabled}")
    else:
        # 如果实例已存在，更新RAG状态
        vet_chat_instances[instance_key].rag = rag_enabled
        vet_chat_instances[instance_key].state["rag"] = rag_enabled
        print(f"🔄 更新 VetChat RAG状态: {rag_enabled}")
    
    #检查vet_chat_instances是否存在
    #if True:
    #    print(f"🔍 [APP] vet_chat_instances: {vet_chat_instances}")
    return vet_chat_instances[instance_key]

def get_or_create_animal_hospital(user_id: Optional[str] = None, task_id: Optional[str] = None) -> AnimalHospital:
    """获取或创建 AnimalHospital 实例"""
    # 用户ID由用户输入，如果没有则使用默认值
    actual_user_id = user_id or "anonymous_user"
    
    # 对话ID随机生成（如果task_id存在则使用，否则生成新的）
    if task_id:
        actual_conv_id = task_id
    else:
        actual_conv_id = f"conv_{uuid.uuid4().hex[:8]}"
    
    # 使用 user_id + conv_id 作为实例的唯一键
    instance_key = f"{actual_user_id}:{actual_conv_id}"
    
    #实例化AnimalHospital
    if instance_key not in animal_hospital_instances:
        animal_hospital_instances[instance_key] = AnimalHospital(
            user_id=actual_user_id, 
            conv_id=actual_conv_id
        )
        print(f"✅ 创建新的 AnimalHospital 实例: user_id={actual_user_id}, conv_id={actual_conv_id}")
    
    return animal_hospital_instances[instance_key]

# -------------------------------
# 请求模型
# -------------------------------
class MessageRequest(BaseModel):
    message: str
    mode: Optional[str] = "vet"  # "animal" 或 "vet"
    user_id: Optional[str] = None  # 用户ID
    task_id: Optional[str] = None  # 任务ID
    rag_enabled: Optional[bool] = False  # RAG知识库开关

# -------------------------------
# 页面路由
# -------------------------------
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/admin")
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

# -------------------------------
# 消息接口
# -------------------------------
@app.post("/send_message")
async def send_message(req: MessageRequest):
    user_input = req.message
    mode = (req.mode or "vet").lower()
    user_id = req.user_id
    task_id = req.task_id
    rag_enabled = req.rag_enabled

    async with state_lock:
        if mode == "vet":
            # 获取或创建 VetChat 实例
            vet_chat_instance = get_or_create_vet_chat(user_id, task_id, rag_enabled)
            await vet_chat_instance.set_user_input(user_input)

            ai_response = ""
            awaiting_input = False
            ended = False

            # 使用修改后的 VetChat 运行方式
            try:
                print(f"🚀 [APP] 开始执行VET图，当前state keys: {list(vet_chat_instance.state.keys())}")
                print(f"🔍 [APP] 图执行前current_output: {vet_chat_instance.state['current_output']}")
                
                event_count = 0
                async for event in vet_chat_instance.compiled_graph.astream(vet_chat_instance.state):
                    # 先处理普通节点事件：把 event[key] 写回全局 state
                    for key, value in event.items():
                        if key not in ("__end__", "__interrupt__"):
                            vet_chat_instance.state = value

                    # 再读取 current_output
                    current_output = vet_chat_instance.state.get("current_output")

                    #print("#"*50)
                    #print(f"🔍 [APP] 检查current_output: {current_output}")

                    if current_output:
                        ai_response = current_output

                    if "__end__" in event:
                        vet_chat_instance.state = event["__end__"]
                        break

                    if "__interrupt__" in event:
                        awaiting_input = True
                        break
                        
                    # 如果结束标志
                    if vet_chat_instance.state.get("end", False):
                        ended = True
                        break
                                
                # 获取最终响应
                final_output = vet_chat_instance.state.get("current_output", "")
                print(f"🎯 [APP] 最终获取的输出: {final_output}")
                
                ai_response = final_output
                if isinstance(ai_response, list):
                    ai_response = "".join(map(str, ai_response))
                    
                ended = vet_chat_instance.state.get("end", False)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=500)

            return {
                "response": ai_response,
                "awaiting_input": awaiting_input,
                "ended": ended,
            }
        
        #模拟动物医院模式
        else:
            # animal 模式使用新的 AnimalHospital 类
            animal_hospital_instance = get_or_create_animal_hospital(user_id, task_id)
            animal_hospital_instance.set_user_input(user_input)

            ai_response = ""
            awaiting_input = False
            ended = False

            try:
                async for event in animal_hospital_instance.compiled_graph.astream(animal_hospital_instance.state):
                    # 检查当前事件来自哪个节点
                    current_node = None
                    for key in event.keys():
                        if key not in ("__end__", "__interrupt__"):
                            current_node = key
                            break
                    
                    # 只在 reception、doctor、diagnosis、chat 节点时采纳输出
                    if current_node in ["reception", "doctor", "diagnosis", "chat"]:
                        new_state = event[current_node]
                        if new_state.get("current_output"):
                            ai_response = new_state["current_output"]
                    
                    # 更新状态
                    for key, value in event.items():
                        if key not in ("__end__", "__interrupt__"):
                            animal_hospital_instance.state = value
                    
                    if "__end__" in event:
                        animal_hospital_instance.state = event["__end__"]
                    if "__interrupt__" in event:
                        awaiting_input = True
                        break
                    # 如果结束标志
                    if animal_hospital_instance.state.get("end", False):
                        ended = True
                        break
                
                # 获取最终响应（保持原有逻辑）
                if isinstance(ai_response, list):
                    ai_response = "\n".join(map(str, ai_response))
                ended = animal_hospital_instance.state.get("end", False)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=500)

            return {
                "response": ai_response,
                "awaiting_input": awaiting_input,
                "ended": ended,
            }

# -------------------------------
# 流式消息接口（SSE）
# -------------------------------
@app.post("/send_message_stream")
async def send_message_stream(req: MessageRequest):
    """使用 Server-Sent Events 进行流式输出"""
    user_input = req.message
    mode = (req.mode or "vet").lower()
    user_id = req.user_id
    task_id = req.task_id
    rag_enabled = req.rag_enabled
    
    async def event_generator():
        """生成 SSE 事件流"""
        try:
            if mode == "vet":
                # 获取或创建 VetChat 实例
                vet_chat_instance = get_or_create_vet_chat(user_id, task_id, rag_enabled)
                await vet_chat_instance.set_user_input(user_input)
                
                ai_response = ""
                awaiting_input = False
                ended = False
                
                # 使用 astream_events 进行 token 级别流式输出
                async for event in vet_chat_instance.compiled_graph.astream_events(
                    vet_chat_instance.state,
                    version="v2"
                ):
                    kind = event.get("event")
                    
                    # 捕获 LLM 流式输出
                    if kind == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        if content:
                            ai_response += content
                            # 发送 token 数据
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                    
                    # 捕获节点完成事件
                    elif kind == "on_chain_end":
                        name = event.get("name", "")
                        if "user" in name:
                            yield f"data: {json.dumps({'type': 'node', 'node': 'user'})}\n\n"
                        elif "vet_chatbot" in name:
                            yield f"data: {json.dumps({'type': 'node', 'node': 'vet_chatbot'})}\n\n"
                    
                    # 更新最终状态
                    if kind == "on_chain_end" and event.get("name") == "LangGraph":
                        output = event.get("data", {}).get("output", {})
                        if output:
                            vet_chat_instance.state.update(output)
                            if output.get("end"):
                                ended = True
                
                # 发送完成信号
                yield f"data: {json.dumps({'type': 'done', 'response': ai_response, 'awaiting_input': awaiting_input, 'ended': ended})}\n\n"
                
            else:
                # animal 模式的流式输出（模仿vet模式）
                animal_hospital_instance = get_or_create_animal_hospital(user_id, task_id)
                animal_hospital_instance.set_user_input(user_input)
                
                ai_response = ""
                awaiting_input = False
                ended = False
                current_node = None  # 跟踪当前节点
                valid_nodes = ["reception", "doctor", "diagnosis", "chat"]  # 指定需要输出的节点
                
                # 使用 astream_events 进行 token 级别流式输出
                async for event in animal_hospital_instance.compiled_graph.astream_events(
                    animal_hospital_instance.state,
                    version="v2"
                ):
                    kind = event.get("event")
                    name = event.get("name", "")
                    metadata = event.get("metadata", {})
                    
                    # 从 metadata 中获取 langgraph_node
                    langgraph_node = metadata.get("langgraph_node", "")
                    
                    # 跟踪节点的开始和结束
                    if kind == "on_chain_start":
                        node_name = langgraph_node or name
                        if node_name in valid_nodes:
                            # 每次进入指定节点时，如果上一个节点已结束
                            if current_node is None:
                                ai_response = ""
                                # 发送clear信号，通知前端清空上一轮的显示
                                yield f"data: {json.dumps({'type': 'clear', 'node': node_name})}\n\n"
                            current_node = node_name
                    
                    elif kind == "on_chain_end":
                        node_name = langgraph_node or name
                        if node_name in valid_nodes:
                            # 只在指定节点结束时才发送节点完成事件
                            if current_node == node_name:
                                yield f"data: {json.dumps({'type': 'node', 'node': node_name})}\n\n"
                            # 节点结束时重置current_node
                            current_node = None
                    
                    # 只在指定节点时才进行流式输出
                    if kind == "on_chat_model_stream" and current_node in valid_nodes:
                        content = event["data"]["chunk"].content
                        if content:
                            ai_response += content
                            # 发送 token 数据
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                    
                    # 检测图执行完成
                    if kind == "on_chain_end" and name == "LangGraph":
                        output = event.get("data", {}).get("output", {})
                        if output:
                            animal_hospital_instance.state.update(output)
                            # 只在流式输出为空时才使用 current_output（避免覆盖已流式输出的内容）
                            if not ai_response and output.get("current_output"):
                                ai_response = output["current_output"]
                            if output.get("end"):
                                ended = True
                
                # 流式输出完成后，判断是否需要等待输入
                # 如果没有新的输出且未结束，说明遇到了interrupt
                if not ai_response and not ended:
                    awaiting_input = True
                
                # 只有当有响应内容时才发送完成信号
                if ai_response:
                    #print(f"🎯 [APP] 完成信号: {ai_response}, {awaiting_input}, {ended}")
                    yield f"data: {json.dumps({'type': 'done', 'response': ai_response, 'awaiting_input': awaiting_input, 'ended': ended})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# -------------------------------
# 会话重置接口
# -------------------------------
@app.post("/reset")
async def reset(request: Request):
    try:
        data = await request.json()
        mode = (data.get("mode") or "animal").lower()
        user_id = data.get("user_id")
        task_id = data.get("task_id")
    except Exception:
        mode = "animal"
        user_id = None
        task_id = None

    async with state_lock:
        if mode == "vet":
            # 清除指定用户的 VetChat 实例
            if user_id and task_id:
                instance_key = f"{user_id}:{task_id}"
                if instance_key in vet_chat_instances:
                    del vet_chat_instances[instance_key]
                    print(f"✅ VetChat 会话已重置: {instance_key}")
            else:
                # 如果没有指定用户，清除所有实例
                vet_chat_instances.clear()
                print("✅ 所有 VetChat 会话已重置")
        else:
            # 清除指定用户的 AnimalHospital 实例
            if user_id and task_id:
                instance_key = f"{user_id}:{task_id}"
                if instance_key in animal_hospital_instances:
                    del animal_hospital_instances[instance_key]
                    print(f"✅ AnimalHospital 会话已重置: {instance_key}")
            else:
                # 如果没有指定用户，清除所有实例
                animal_hospital_instances.clear()
                print("✅ 所有 AnimalHospital 会话已重置")

    print(f"[系统]: 会话已重置 -> {mode}")
    return {"status": "ok", "mode": mode}
