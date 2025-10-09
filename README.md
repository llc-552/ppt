# 🐾 Veta - 智能体动物医院

<p align="center">
  <img src="main/static/1.png" alt="Veta Logo" width="200"/>
</p>

<p align="center">
  <strong>基于 LangGraph 的智能宠物医疗问诊系统</strong>
</p>

<p align="center">
  <a href="#特性">特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#配置说明">配置说明</a> •
  <a href="#项目结构">项目结构</a> •
  <a href="#使用文档">使用文档</a>
</p>

---

## 📖 项目简介

Veta 是一个基于 LangGraph 和大语言模型构建的智能宠物医疗问诊系统。系统提供两种工作模式：

### 快速体验
https://45e70408d333.ngrok-free.app/

1. **模拟问诊模式**：模拟完整的宠物医院就诊流程，包括前台接待、科室分诊、医生问诊和诊断
2. **兽医问答模式**：直接提供专业的兽医咨询服务，支持 RAG 知识库检索增强

> 💡 **快速提示**：本项目使用 Conda 环境管理，支持本地开发（`local.sh`）和公网访问（`ngrok.sh`）两种启动方式。

## ✨ 特性

### 🎯 核心功能
- **多智能体协作**：基于 LangGraph 的多 Agent 系统，模拟真实医院工作流程
- **RAG 知识库**：集成 FAISS 向量检索和 BM25 混合检索，提供专业的医疗知识支持
- **对话记忆管理**：基于 Redis 的持久化对话存储，支持多用户会话管理
- **流式响应**：Server-Sent Events (SSE) 实现的实时流式输出
- **双模式切换**：灵活切换模拟问诊和兽医问答模式

### 🛠️ 技术特点
- **配置化管理**：YAML 配置文件管理 API、模型参数等配置
- **响应式 UI**：现代化的 Web 界面，支持桌面端和移动端
- **任务管理**：支持多任务创建、切换和历史记录查看
- **知识库管理**：智能文档加载、分块、索引和检索

### 🎨 用户界面
- 类似 Gemini 的现代化聊天界面
- 侧边栏任务管理（今天/昨天/过去7天分组）
- 实时流式消息显示
- 知识库检索开关
- 用户数据管理后台

## 🚀 快速开始

### 环境要求

- Anaconda 或 Miniconda
- Redis 服务器（项目自带）
- 足够的磁盘空间用于向量索引（建议 2GB+）
- （可选）ngrok 用于公网访问

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/Jimmy0743/Veta.git
cd veta
```

2. **创建 Conda 环境**
```bash
# 创建名为 veta 的 conda 环境，指定 Python 3.12+
conda create -n veta python=3.12

# 激活环境
conda activate veta
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置文件设置**
```bash
# 复制配置示例文件
cp config.example.yaml config.yaml

# 编辑配置文件，填入你的 API Key
vim config.yaml  # 或使用其他编辑器
```

5. **准备 RAG 数据（可选）**
```bash
# 将文档放入 rag_data 目录
mkdir -p rag_data
cp your_documents/* rag_data/
```

6. **启动应用**

> ⚠️ **重要**：在运行启动脚本前，确保已激活 conda 环境：`conda activate veta`

**方式一：本地运行（推荐用于开发）**
```bash
./local.sh
```
- 启动 Redis 服务器（端口 6378）
- 启动 Uvicorn 服务器（端口 3367）
- 支持热重载

**方式二：公网访问（通过 ngrok）**

> 📝 **首次使用需配置 ngrok authtoken**
> ```bash
> # 1. 访问 https://ngrok.com/ 注册并获取 authtoken
> # 2. 进入 Ngrok 目录配置 token（只需配置一次）
> cd Ngrok
> ./ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
> cd ..
> ```

```bash
./ngrok.sh
```
- 启动 Redis 服务器（端口 6378）
- 启动 Uvicorn 服务器（端口 5555）
- 启动 ngrok 隧道，提供公网访问地址
- 自动处理端口冲突

7. **访问应用**

**本地运行（local.sh）**
```
浏览器打开: http://localhost:3367
管理后台: http://localhost:3367/admin
```

**公网访问（ngrok.sh）**
```
公网地址: 启动后终端会显示 ngrok 生成的 https 地址
本地地址: http://localhost:5555
ngrok控制台: http://localhost:4040
管理后台: https://your-ngrok-url/admin
```

### 停止服务

**停止 local.sh 启动的服务**
```bash
# 按 Ctrl+C 停止 uvicorn
# 手动停止 Redis
cd redis/redis-8.0.0
src/redis-cli -p 6378 shutdown
```

**停止 ngrok.sh 启动的服务**
```bash
# 方法一：使用启动时显示的 PID
kill <UVICORN_PID> <NGROK_PID>

# 方法二：杀死所有相关进程
pkill -f uvicorn && pkill -f ngrok
cd redis/redis-8.0.0
src/redis-cli -p 6378 shutdown
```

### 故障排查

**端口被占用**
```bash
# 查看端口占用情况
lsof -i:3367  # 本地端口
lsof -i:5555  # ngrok 端口
lsof -i:6378  # Redis 端口

# 释放端口
fuser -k 3367/tcp
fuser -k 5555/tcp
```

**ngrok 无法启动**
- 确保已将 ngrok 可执行文件放在 `Ngrok/` 目录下
- **检查是否配置了 authtoken**：
  ```bash
  cd Ngrok
  ./ngrok config check  # 查看配置是否有效
  cat ~/.config/ngrok/ngrok.yml  # 查看当前配置的 token
  ```
- 检查 ngrok 日志：`cat ngrok.log`
- 访问 ngrok 控制台：http://localhost:4040
- 如需重新配置 token：`cd Ngrok && ./ngrok config add-authtoken YOUR_TOKEN`

**Redis 连接失败**
```bash
# 检查 Redis 是否运行
ps aux | grep redis-server

# 手动启动 Redis
cd redis/redis-8.0.0
src/redis-server --port 6378 --daemonize yes
```

## ⚙️ 配置说明

### 配置文件结构

编辑 `config.yaml` 文件来配置系统：

```yaml
# OpenAI API 配置
openai:
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: "your-api-key-here"  # 替换为你的 API Key
  model: "qwen-plus"
  temperature: 0.9

# Redis 配置
redis:
  host: "127.0.0.1"
  port: 6378

# RAG 配置
rag:
  folder_path: "./rag_data"
  index_path: "./faiss_index"
  embedding_model: "Qwen/Qwen3-Embedding-0.6B"
  rerank_model: "BAAI/bge-reranker-base"
  device: "cpu"  # 或 "cuda" 如果有 GPU
```

详细配置说明请查看 [CONFIG_README.md](CONFIG_README.md)

### 环境变量（可选）

你也可以使用环境变量来覆盖配置：

```bash
# 确保在 veta conda 环境中
conda activate veta

# 设置环境变量
export OPENAI_API_KEY="your-api-key"
export REDIS_HOST="localhost"
export REDIS_PORT="6378"
```

### Conda 环境管理

```bash
# 激活环境
conda activate veta

# 退出环境
conda deactivate

# 删除环境（如需重建）
conda env remove -n veta

# 查看已安装的包
conda list
```

## 📁 项目结构

```
veta/
├── config.yaml             # 配置文件（需自行创建）
├── config.example.yaml     # 配置示例
├── requirements.txt        # Python 依赖
├── README.md               # 项目说明
├── CONFIG_README.md        # 配置系统详细说明
├── .gitignore              # Git 忽略文件
│
├── local.sh                # 本地开发启动脚本（推荐）
├── ngrok.sh                # 公网访问启动脚本（带 ngrok）
├── start.sh                # 通用启动脚本（旧版）
├── start.bat               # Windows 启动脚本（旧版）
├── cleanup.sh              # 清理脚本
│
├── main/                   # 主要代码目录
│   ├── __init__.py        # Python 包初始化
│   ├── app.py             # FastAPI 主应用
│   ├── vet.py             # 兽医问答模式实现
│   ├── animal_hospital.py # 模拟问诊模式实现
│   ├── rag.py             # RAG 检索系统
│   ├── chatstore.py       # 对话存储管理
│   ├── prompt.py          # 系统提示词
│   ├── config.py          # 配置管理模块
│   │
│   ├── templates/         # HTML 模板
│   │   ├── index.html    # 主页面
│   │   └── admin.html    # 管理后台
│   │
│   └── static/            # 静态资源
│       ├── veta.css      # 样式文件
│       ├── veta.js       # 主要 JavaScript
│       ├── user-storage.js # 用户数据管理
│       └── 1.png         # Logo 图片
│
├── rag_data/              # RAG 知识库文档
├── faiss_index/           # FAISS 向量索引（自动生成）
└── redis/                 # Redis 数据目录（可选）
```

## 📚 使用文档

### 兽医问答模式

1. 进入系统后选择"兽医问答"模式
2. 可选择性开启"知识库检索"增强回答
3. 直接输入宠物健康问题
4. 系统会基于专业知识给出建议

### 模拟问诊模式

1. 选择"模拟问诊"模式
2. 系统会模拟以下流程：
   - 前台接待：收集宠物基本信息
   - 科室分诊：判断应该挂哪个科室
   - 医生问诊：详细询问病情
   - 诊断结果：给出初步诊断和建议

### RAG 知识库使用

1. 将文档（PDF、TXT、DOCX、MD）放入 `rag_data/` 目录
2. 系统会自动：
   - 检测文档变化
   - 切分文档内容
   - 生成向量索引
   - 支持混合检索（BM25 + FAISS）
3. 在兽医问答模式中开启知识库检索开关

### 管理后台

访问 `/admin` 可以：
- 查看所有用户数据
- 导出用户对话记录
- 清理历史数据
- 查看存储使用情况

## 🔧 开发指南

### 添加新的问诊模式

1. 在 `main/` 目录下创建新的 Python 文件
2. 在对应文件中定义新的节点
3. 在 `StateGraph` 中添加节点和边
4. 更新 `main/prompt.py` 添加相应的提示词

### 自定义 RAG 检索

在 `main/rag.py` 中修改：
- `chunk_size`：文档切片大小
- `top_n`：返回结果数量
- `embedding_model`：向量模型
- `rerank_model`：重排序模型

### 扩展 API

在 `main/app.py` 中添加新的路由：

```python
@app.post("/your_endpoint")
async def your_endpoint(request: YourRequest):
    # 实现逻辑
    return {"result": "success"}
```

## 🤝 贡献指南

欢迎贡献！请遵循以下步骤：

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

更多详情请查看 [CONTRIBUTING.md](CONTRIBUTING.md)

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - 多智能体框架
- [LangChain](https://github.com/langchain-ai/langchain) - LLM 应用开发框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化 Web 框架
- [FAISS](https://github.com/facebookresearch/faiss) - 高效向量检索

## 📧 联系方式

- 项目主页: [GitHub Repository](https://github.com/yourusername/veta)
- 问题反馈: [Issues](https://github.com/yourusername/veta/issues)

---

<p align="center">
  Made with ❤️ by Veta Team
</p>
