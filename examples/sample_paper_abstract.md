# Benchmarking Large Language Models on Clinical NLP Tasks

## Abstract

We systematically evaluate five large language models (GPT-4, Claude, Gemini,
LLaMA-3, and PaLM-2) on three clinical NLP tasks: named entity recognition,
relation extraction, and medical question answering.

## Methods

- **Models**: GPT-4, Claude-3, Gemini-2.0, LLaMA-3-70B, PaLM-2
- **Datasets**: MIMIC-III, PubMedQA, MedQA
- **Metrics**: Accuracy, F1, BLEU, ROUGE-L
- **Fine-tuning**: LoRA with rank=16, learning rate 5e-4

## Results

| Model    | NER (F1) | RE (F1) | QA (Acc) |
| -------- | -------- | ------- | -------- |
| GPT-4    | 0.92     | 0.88    | 0.86     |
| Claude-3 | 0.91     | 0.89    | 0.85     |
| LLaMA-3  | 0.89     | 0.85    | 0.82     |

## Limitations

- Limited to English clinical texts only
- Evaluation on academic benchmarks may not reflect real-world performance
- Model outputs were not reviewed by clinical experts
