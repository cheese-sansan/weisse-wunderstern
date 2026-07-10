# clinical NLP benchmark evaluation 研究报告

> 样例输入：[sample_paper_abstract.md](sample_paper_abstract.md)
>
> 数据模式：**混合来源（原始文档 + 显式模拟数据）**

## 文档证据提炼

以下数值由无 LLM 的确定性解析器直接读取 Results 表格，并统一引用 `[D1]`：

| 模型 | NER F1 | RE F1 | QA Accuracy | 来源 |
| --- | ---: | ---: | ---: | --- |
| GPT-4 | 0.92 | 0.88 | 0.86 | [D1] |
| Claude-3 | 0.91 | 0.89 | 0.85 | [D1] |
| LLaMA-3 | 0.89 | 0.85 | 0.82 | [D1] |

## 方法与限制

- 文档明确列出 MIMIC-III、PubMedQA 和 MedQA 数据集。[D1]
- 文档明确列出 LoRA rank 16、学习率 `5e-4`。[D1]
- 研究仅覆盖英文临床文本，且未由临床专家复核模型输出。[D1]
- 上述内容只表示原文陈述；NoteForge 未独立验证实验真实性。

## 模拟文献边界

该演示使用 `--provider mock` 验证离线流程。任何 `[L*]` 记录均为 `simulated`，不得用于支持上述文档事实；文档事实仅引用 `[D1]`。

## 数据来源

- [D1] `sample_paper_abstract.md` — `local-file/source_document`。

> 本样例展示原始文档证据与模拟检索结果的隔离，不构成临床或模型采购建议。
