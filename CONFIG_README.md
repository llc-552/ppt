# 配置系统使用说明

## 📋 概述

本项目现在支持通过 `config.yaml` 配置文件来管理所有模型 API、Redis 连接、RAG 参数等配置项。这样可以方便地修改配置而无需改动代码。

## 🚀 快速开始

### 1. 安装依赖

首先确保安装了 `pyyaml` 依赖：

```bash
pip install pyyaml==6.0.1
```

或者重新安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 创建配置文件

项目根目录下已有 `config.example.yaml` 示例文件。您可以：

**方法一：复制示例文件**
```bash
cp config.example.yaml config.yaml
```

**方法二：使用已有的 config.yaml**
项目中已经创建了 `config.yaml` 文件，包含了当前使用的配置。

### 3. 修改配置

编辑 `config.yaml` 文件，修改您需要的配置项：

```yaml
# OpenAI API 配置
openai:
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: "your-api-key-here"  # 修改为您的实际 API Key
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
  bm25_k: 5
  faiss_k: 5
  top_n: 1
  chunk_size: 500
  chunk_overlap: 50
  device: "cpu"

# VetChat 配置
vetchat:
  max_tokens: 384
  max_summary_tokens: 128
  trim_max_tokens: 2500
```

## 📁 配置文件结构

### OpenAI 配置 (`openai`)
- `api_base`: API 基础地址
- `api_key`: API 密钥（**重要：请妥善保管**）
- `model`: 使用的模型名称
- `temperature`: 温度参数（0-2，越高越随机）

### Redis 配置 (`redis`)
- `host`: Redis 服务器地址
- `port`: Redis 服务器端口

### RAG 配置 (`rag`)
- `folder_path`: RAG 数据目录
- `index_path`: FAISS 索引存储目录
- `embedding_model`: 文本向量化模型
- `rerank_model`: 结果重排序模型
- `bm25_k`: BM25 检索返回的结果数量
- `faiss_k`: FAISS 检索返回的结果数量
- `top_n`: 最终保留的结果数量
- `chunk_size`: 文本切片大小（字符数）
- `chunk_overlap`: 文本切片重叠大小（字符数）
- `device`: 使用的设备（`cpu` 或 `cuda`）

### VetChat 配置 (`vetchat`)
- `max_tokens`: 记忆最大 token 数
- `max_summary_tokens`: 摘要最大 token 数
- `trim_max_tokens`: 消息裁剪最大 token 数

## 💻 代码中使用配置

配置系统已经集成到以下文件中：
- `vet.py` - VetChat 类
- `rag.py` - Retriever 类
- `animal_hospital.py` - AnimalHospital 类
- `app.py` - FastAPI 应用

### 在代码中读取配置

如果需要在其他模块中使用配置，可以这样导入：

```python
from config import get_openai_config, get_redis_config, get_rag_config, get_vetchat_config

# 获取完整配置
openai_config = get_openai_config()
print(openai_config['api_key'])

# 或获取单个配置项
from config import get_config
api_key = get_config('openai.api_key')
```

### 配置读取优先级

程序会按以下优先级读取配置：
1. 代码中显式传入的参数（如果有）
2. `config.yaml` 配置文件
3. 代码中的默认值

例如，在创建 VetChat 实例时：
```python
# 使用配置文件中的 Redis 配置
vet_chat = VetChat(user_id="user1")

# 或者覆盖配置文件中的值
vet_chat = VetChat(user_id="user1", redis_host="192.168.1.100", redis_port=6379)
```

## 🔒 安全建议

1. **不要提交包含真实 API Key 的配置文件到版本控制系统**
   ```bash
   # 将 config.yaml 添加到 .gitignore
   echo "config.yaml" >> .gitignore
   ```

2. **使用环境变量（可选）**
   
   如果需要更高的安全性，可以扩展配置系统支持环境变量。

3. **定期更换 API Key**
   
   定期更新 API 密钥，确保安全性。

## 🛠️ 测试配置

您可以运行配置测试脚本来验证配置是否正确：

```bash
python config.py
```

这将打印所有配置项，帮助您确认配置是否正确加载。

## ❓ 常见问题

### Q: 修改配置后需要重启服务吗？
A: 是的，配置文件在程序启动时加载，修改后需要重启服务才能生效。

### Q: 配置文件找不到怎么办？
A: 确保 `config.yaml` 文件位于项目根目录（与 `vet.py`、`app.py` 等文件同级）。

### Q: 如何重新加载配置？
A: 可以调用 `config.reload()` 方法：
```python
from config import config
config.reload()
```

### Q: 配置文件格式错误怎么办？
A: 确保 YAML 格式正确，注意缩进必须使用空格（不能用 Tab），键值对之间要有空格。

## 📝 更新日志

- 创建了配置管理系统
- 支持 YAML 格式配置文件
- 集成到所有主要模块中
- 添加了配置示例文件
- 提供了配置读取的便捷函数

