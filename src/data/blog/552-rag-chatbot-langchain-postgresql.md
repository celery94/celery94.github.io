---
pubDatetime: 2025-02-25
title: "如何使用 LangChain 和 PostgreSQL 构建 RAG 聊天机器人"
description: "本文详细介绍了如何结合 LangChain 框架和 PostgreSQL（pgvector 扩展）构建一个基于检索增强生成（RAG）的聊天机器人，涵盖数据准备、向量存储、检索链构建和部署等完整流程。"
tags: ["RAG", "LangChain", "PostgreSQL", "AI", "LLM"]
slug: "rag-chatbot-langchain-postgresql"
source: "https://dev.to/code_2/how-to-create-a-rag-powered-chatbot-with-langchain-and-postgresql-51l9"
---

## 检索增强生成（RAG）简介

在人工智能快速发展的今天，聊天机器人已经成为客户服务、信息检索和交互应用中不可或缺的工具。传统聊天机器人通常依赖规则系统或简单的机器学习模型，在处理需要最新知识或特定领域信息的复杂查询时往往力不从心。检索增强生成（RAG）由此应运而生。RAG 是一种混合方法，它将检索系统的优势与生成式 AI 模型相结合，让聊天机器人能够在对话过程中动态访问外部知识库。

RAG 的核心工作原理是：先从大规模数据语料中检索相关信息，再利用这些信息来增强送入大语言模型（LLM）的提示词。这种方式解决了独立 LLM 的关键局限性，比如"幻觉"问题（模型生成看似合理但实际错误的信息）以及无法整合实时或私有数据的问题。通过引入检索机制，RAG 确保了响应基于真实数据，使其更加准确可靠。

RAG 的概念最早由 Facebook AI Research（现 Meta AI）在 2020 年的论文中提出，此后被广泛优化并应用于生产系统。在实践中，构建 RAG 聊天机器人包含几个步骤：数据摄入与处理、创建向量嵌入用于语义搜索、将嵌入存储到向量数据库、在查询时检索相关片段，以及使用 LLM 生成响应。本文将引导你使用 LangChain（一个流行的 LLM 应用开发框架）和带有向量能力的 PostgreSQL 完成整个构建过程。

为什么选择 LangChain 和 PostgreSQL？LangChain 提供了模块化组件，可以将检索、生成和其他 AI 任务串联起来，让开发直观且可扩展。PostgreSQL 配合 pgvector 扩展，提供了强大的开源向量存储和相似性搜索方案，在很多场景下无需使用 Pinecone 或 Weaviate 等专用向量数据库。这个组合具有高性价比、高性能，且易于集成到现有关系数据库工作流中。

## 认识 LangChain：LLM 应用开发框架

LangChain 是一个开源框架，旨在简化大语言模型驱动应用的开发。它由 Harrison Chase 创建，目前由活跃的社区维护。LangChain 抽象了将 LLM 与外部工具、数据源和工作流集成的大量复杂性，允许开发者将提示词、模型、检索器和代理等各种组件"链式"组合，创建复杂的 AI 管道。

LangChain 的关键特性之一是模块化。它的组件包括：

- **Document Loaders**：从各种来源（PDF、网页、数据库等）加载数据
- **Text Splitters**：将大段文本拆分为可管理的块
- **Embeddings**：将文本转换为向量表示
- **Vector Stores**：管理向量的存储和查询

对于 RAG 场景，LangChain 的 `RetrievalQA` 链是核心利器，可以无缝集成检索和生成流程。

LangChain 支持多种 LLM 提供商，包括 OpenAI、Hugging Face 和 Anthropic，可以根据成本、性能或其他考量灵活选择模型。它还包含会话记忆管理工具（对维持聊天上下文至关重要），以及评估和调试工具。

在我们的 RAG 聊天机器人中，LangChain 将作为编排层：加载文档、使用 OpenAI 的 `text-embedding-ada-002` 等模型生成嵌入、将嵌入存入 PostgreSQL，并构建一条检索链在传给 LLM 生成响应之前先查询数据库获取相关信息。

安装 LangChain：

```bash
pip install langchain
```

根据你选择的 LLM 提供商，可能还需要安装额外的包，如 `langchain-openai`。

## PostgreSQL 作为向量数据库：借助 pgvector

PostgreSQL 是目前最可靠、功能最丰富的开源关系数据库之一。虽然传统上用于结构化数据，但 pgvector 扩展的引入使 PostgreSQL 变成了一个能力出色的向量数据库，非常适合 RAG 应用中的语义搜索。pgvector 添加了对向量数据类型、索引和相似性运算（如余弦距离和欧几里得距离）的支持。

为什么用 PostgreSQL 存储向量？它在生产环境中久经考验，支持 ACID 事务，并能与现有 SQL 工作流无缝集成。与专用向量数据库不同，PostgreSQL 允许你在同一张表中将元数据与向量一起存储，简化了需要结合语义搜索和传统过滤条件（如日期范围或用户 ID）的查询。pgvector 扩展轻量级，通过一条简单的 SQL 命令即可安装：

```sql
CREATE EXTENSION vector;
```

在我们的设置中，将创建一张表来存储文档块的文本、嵌入向量列（例如 `VECTOR(1536)` 对应 OpenAI 嵌入），以及任何元数据。为了高效检索，需要在向量列上添加 IVFFlat 或 HNSW 索引。HNSW（分层可导航小世界）对高维向量特别有效，提供快速的近似最近邻搜索。

要将 LangChain 与 PostgreSQL 连接，我们使用 LangChain 的 PGVector 向量存储包装器，它在底层处理嵌入的存储和检索。安装方式：

```bash
pip install langchain-postgres psycopg2-binary
```

PostgreSQL 配合 pgvector 让向量搜索变得普惠化，开发者无需担心厂商绑定或额外基础设施成本。

## 搭建开发环境

在编写代码之前，先确保环境就绪。你需要 Python 3.8 或更高版本。首先创建虚拟环境：

```bash
python -m venv rag_env
```

安装核心依赖：

```bash
pip install langchain langchain-openai langchain-postgres openai psycopg2-binary pgvector
```

如果使用其他嵌入模型，需要做相应调整（例如开源方案需要 `sentence-transformers`）。本指南默认使用 OpenAI，因此需要将 API 密钥设为环境变量：

```bash
export OPENAI_API_KEY='your-key-here'
```

接下来搭建 PostgreSQL。如果尚未安装，可以从官网下载，也可以使用 Docker 简化安装。一个简单的 `docker-compose.yml` 配置如下：

```yaml
version: '3'
services:
  db:
    image: ankane/pgvector
    ports:
      - 5432:5432
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: rag_db
```

运行 `docker-compose up` 即可启动，该镜像已预装 pgvector。

对于聊天机器人界面，我们使用 Streamlit 构建简单的 Web 应用：

```bash
pip install streamlit
```

## 数据准备与摄入

数据是任何 RAG 系统的基础。假设我们要构建一个基于 AI 伦理研究论文集合的问答聊天机器人。首先收集文档（PDF、文本文件或网页抓取内容）。

LangChain 的 Document Loaders 让数据摄入非常简单。例如，加载一个目录下的 PDF 文件：

```python
from langchain.document_loaders import PyPDFDirectoryLoader

loader = PyPDFDirectoryLoader("path/to/docs")
docs = loader.load()
```

这会返回一个 Document 对象列表，每个对象包含 `page_content` 和 `metadata`。

接下来，将文档拆分为块。大段文本需要拆分以适应 LLM 上下文窗口并提升检索精度。使用 `RecursiveCharacterTextSplitter`：

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)
chunks = text_splitter.split_documents(docs)
```

这里 `chunk_size=1000` 表示每个块约 1000 个字符，200 个字符的重叠保证上下文连续性。可根据领域特点调整参数。

预处理也很重要：清除页眉、页脚或噪声文本。可以在加载器中或加载完成后添加自定义逻辑。

元数据丰富化能增添价值。为每个块附加来源、页码或标签：

```python
for chunk in chunks:
    chunk.metadata["source"] = "AI_Ethics_Paper_2023"
```

这些元数据可以在查询时使用，比如按日期过滤。

## 生成语义搜索嵌入

嵌入是文本的数值表示，能够捕获语义信息并支持相似性搜索。在 RAG 中，我们对文档块和用户查询都进行嵌入，然后找到最相似的匹配。

LangChain 集成了多种嵌入提供商。使用 OpenAI：

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
```

嵌入文档块：

```python
embedded_chunks = embeddings.embed_documents([chunk.page_content for chunk in chunks])
```

实际操作中，通常在存储时一并完成嵌入。嵌入是高维向量（例如 ada-002 为 1536 维），因此高效存储很关键。

选择嵌入模型时需要权衡：OpenAI 功能强大但有成本；开源方案如 Hugging Face 的 `all-MiniLM-L6-v2` 免费且 CPU 上速度快：

```python
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
```

建议在样本数据上测试嵌入效果，确保能够捕获你所在领域的细微差别。

## 使用 pgvector 在 PostgreSQL 中存储数据

现在来持久化嵌入。LangChain 的 PGVector 负责处理这一步：

首先定义连接字符串：

```python
from langchain_postgres import PGVector

CONNECTION_STRING = "postgresql+psycopg2://user:pass@localhost:5432/rag_db"
COLLECTION_NAME = "ai_ethics_docs"

vectorstore = PGVector.from_documents(
    embedding=embeddings,
    documents=chunks,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
)
```

如果表不存在，会自动创建，然后插入带有嵌入的文档块并处理元数据。

底层表结构大致如下：

```sql
CREATE TABLE langchain_pg_embedding (
    id UUID PRIMARY KEY,
    collection_id UUID,
    embedding VECTOR(1536),
    document TEXT,
    cmetadata JSONB
);
```

为加速查询添加索引：

```sql
CREATE INDEX ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops);
```

可以直接查询向量存储进行测试：

```python
query_embedding = embeddings.embed_query("What are ethical concerns in AI?")
results = vectorstore.similarity_search_by_vector(query_embedding, k=5)
```

这将返回最相似的 5 个块。

对于混合搜索，可以扩展 SQL 过滤条件，如：

```sql
WHERE cmetadata->>'date' > '2023-01-01'
```

通过合理的索引配置，该方案可以扩展到数百万条向量。

## 在 LangChain 中构建检索链

数据存储就绪后，开始创建检索链。LangChain 的 `RetrievalQA` 将检索器和 LLM 组合在一起。

首先设置检索器：

```python
retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 4})
```

然后配置 LLM：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
```

构建检索链：

```python
from langchain.chains import RetrievalQA

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",  # 'stuff' 将文档拼接在一起；备选方案：'map_reduce'、'refine'
    retriever=retriever,
    return_source_documents=True,
)
```

测试效果：

```python
result = qa_chain({"query": "Explain bias in AI systems."})
print(result["result"])
print(result["source_documents"])
```

`stuff` 类型将检索到的文档直接塞入提示词中。对于更长的上下文，`map_reduce` 可以并行摘要。

自定义提示词可以获得更好的响应：

```python
from langchain.prompts import PromptTemplate

prompt_template = """Use the following pieces of context to answer the question. If you don't know, say so.

Context: {context}

Question: {question}

Answer:"""

PROMPT = PromptTemplate(template=prompt_template, input_variables=["context", "question"])

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    chain_type_kwargs={"prompt": PROMPT},
)
```

这能确保响应基于事实、诚实可靠。

## 集成会话记忆以保持上下文

聊天机器人需要记忆功能来处理连续对话。LangChain 的 `ConversationBufferMemory` 用于存储历史记录：

```python
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

conversational_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,
    memory=memory,
)
```

使用示例：

```python
response1 = conversational_chain({"question": "What is AI bias?"})
response2 = conversational_chain({"question": "How to mitigate it?"})
```

第二个查询会利用历史记录获取上下文。对于持久化记忆，可以集成 Redis 或其他存储方案。

这让你的 RAG 系统变成真正的对话代理，像和人交流一样记住之前的对话内容。

## 使用 Streamlit 创建聊天界面

为了让它更具交互性，使用 Streamlit 构建 UI：

```python
import streamlit as st
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_postgres import PGVector
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

# 初始化配置
CONNECTION_STRING = "postgresql+psycopg2://user:pass@localhost:5432/rag_db"
COLLECTION_NAME = "ai_ethics_docs"
embeddings = OpenAIEmbeddings()
vectorstore = PGVector(
    connection=CONNECTION_STRING,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
)
retriever = vectorstore.as_retriever()
llm = ChatOpenAI()
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
chain = ConversationalRetrievalChain.from_llm(llm, retriever, memory=memory)

# Streamlit 应用
st.title("RAG 驱动的 AI 伦理聊天机器人")

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示聊天消息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 用户输入
if prompt := st.chat_input("询问 AI 伦理相关问题："):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            response = chain({"question": prompt})
            st.markdown(response["answer"])
    st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
```

运行 `streamlit run app.py` 即可启动聊天界面。

## 测试与调试

测试至关重要。首先对各组件编写单元测试：

```python
def test_retrieval():
    query = "AI bias"
    results = retriever.get_relevant_documents(query)
    assert len(results) == 4
    assert "bias" in results[0].page_content.lower()
```

使用 LangChain 的评估工具进行端到端测试：

```python
from langchain.evaluation import load_evaluator

evaluator = load_evaluator("qa")
eval_result = evaluator.evaluate_chains([qa_chain], questions=["What is AI ethics?"])
```

常见问题排查：

- **检索效果差**：调整块大小或更换嵌入模型
- **幻觉问题**：强化提示词约束
- **查询速度慢**：优化索引参数

在生产环境中应加入日志监控：添加回调来跟踪查询耗时和检索到的文档。

## 部署与扩展

生产部署可以使用云平台。Streamlit 可以部署在 Heroku 或 Render 上，PostgreSQL 可以使用 AWS RDS。

Docker 容器化配置：

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["streamlit", "run", "app.py"]
```

高流量场景下可使用 PostgreSQL 读副本进行扩展。对于嵌入和 LLM，使用 API 服务可以避免自行托管模型。

安全方面需注意：保护 API 密钥、对输入做清洗以防注入攻击。

成本优化：批量处理嵌入、在适当场景使用更经济的模型。

## RAG 系统最佳实践

以下实践有助于获得最佳性能：

1. **数据质量**：精选高质量来源，去除重复内容
2. **嵌入模型选型**：根据领域匹配模型，必要时进行微调
3. **分块策略**：尝试不同大小，使用语义分块
4. **检索增强**：添加重排序（如 Cohere Rerank）以提升相关性
5. **提示词工程**：精心编写提示词以强调上下文的使用
6. **混合搜索**：将关键词搜索（BM25）与语义搜索结合以增强健壮性
7. **监控**：跟踪嵌入的漂移变化
8. **伦理考量**：确保机器人推崇公平公正

量化等优化手段可以在不显著降低精度的情况下减少成本。

## 进阶主题：定制与扩展

在基础功能之上可以进一步拓展：

添加多模态支持（如使用 CLIP 嵌入处理图像查询）。

集成代理功能，使用 LangChain agents 构建能调用工具的聊天机器人：

```python
from langchain.agents import initialize_agent, Tool

tools = [Tool(name="RAG", func=qa_chain.run, description="Use for AI ethics questions")]
agent = initialize_agent(tools, llm, agent_type="zero-shot-react-description")
```

支持多语言：使用多语言嵌入模型。

利用 HyDE（假设文档嵌入）等技术微调检索器。

对于企业级场景，还需添加用户认证和日志审计功能。

## 总结

使用 LangChain 和 PostgreSQL 构建 RAG 聊天机器人，可以创建智能的、具备上下文感知能力的应用，充分发挥检索和生成两者的优势。从环境搭建到生产部署，本文涵盖了完整的实施流程。

随着 AI 技术的持续演进，RAG 将继续作为核心架构模式不断发展。积极实验、持续迭代、大胆部署，你会发现这个领域有着广阔的可能性。
