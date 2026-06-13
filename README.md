# Lite Agent Orchestrator

轻量级学术文献提炼引擎 —— 从论文和文档中自动提取关键信息，通过多智能体审稿反思生成结构化 Markdown 分析报告。

## 核心能力

- **多格式文档解析**：支持 PDF、DOCX、TXT、Markdown、EPUB 等格式，零依赖基础模式 + 可选高保真解析
- **学术实体抽取**：自动识别论文中的方法、数据集、指标、任务域和实体关系
- **结构化文献检索**：基于关键词和实体生成文献候选（支持 LLM 增强和 Mock 模式）
- **三角色审稿反思**：Extractor 提炼证据 → Critic 审稿质疑 → Synthesizer 综合报告
- **异步 API 服务**：提交-轮询-获取结果的 RESTful 接口，支持并发任务隔离
- **LLM/Mock 双模式**：配置 OpenAI 兼容 API 后启用 LLM 增强，未配置时自动回退

## 快速开始

```bash
# 安装（核心零依赖，仅需 Python 3.10+）
git clone <repo-url>
cd lite-agent-orchestrator

# CLI 模式 — 基于主题分析
python main.py --topic "transformer model evaluation"

# CLI 模式 — 基于文档分析
python main.py --file ./examples/sample_paper_abstract.md

# API 模式 — 启动服务
pip install fastapi uvicorn python-multipart
python main_api.py
```

## API 接口

```bash
# 提交任务
curl -X POST http://localhost:8000/api/v1/jobs/submit -F "topic=AI safety"

# 查询状态
curl http://localhost:8000/api/v1/jobs/status/{job_id}

# 获取报告
curl http://localhost:8000/api/v1/jobs/result/{job_id}
```

## Docker 部署

```bash
docker compose up -d          # 启动 API 服务
docker compose logs -f        # 查看日志
```

## 项目结构

```
├── core/pipeline.py          # 管道执行器（CLI + API 共享）
├── main.py                   # CLI 入口
├── main_api.py               # FastAPI 服务
├── tasks/                    # T0-T4 任务模块
├── utils/                    # 工具模块
├── tests/                    # 55 项单元测试
├── examples/                 # 示例输入
└── docker-compose.yml        # Docker 部署
```

## 文档

- [开发指南](DEVELOPMENT.md) — 详细的项目说明、管道架构、配置
- [演进计划](README_plan.md) — 阶段路线图和验收标准

## 技术栈

Python 3.10+ / FastAPI / Docker — 核心零依赖，Mock 模式持续可用

## License

MIT
