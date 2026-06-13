"""
Weisse Wunderstern — CLI 入口

轻量级智能体任务编排引擎，支持：
- 多任务顺序/动态编排
- 外部文件导入与分析（T0 预处理）
- 状态持久化与断点续跑
- 基于内容感知的动态任务分支
- LLM增强 + Mock兜底双模式
"""

import os
import sys

from utils.env_loader import load_env
from core.pipeline import run_job, PipelineError

load_env()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Weisse Wunderstern - zero-dependency text report analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --topic "2025 自动驾驶行业趋势"
  python main.py --file ./documents/report.pdf
  python main.py --file ./data/notes.txt --topic "AI安全合规分析"
  python main.py --file ./doc.docx --output results/
        """
    )
    parser.add_argument("--topic", "-t", default="", help="研究主题")
    parser.add_argument("--file", "-f", default=None, help="外部文件路径（支持 TXT/MD/JSON/PDF/DOCX）")
    parser.add_argument("--output", "-o", default="outputs", help="job_id / 输出目录名（默认: outputs）")
    parser.add_argument("--tui", action="store_true", help="启动标准库 TUI")

    args = parser.parse_args()

    if args.tui:
        from main_tui import run_tui
        sys.exit(run_tui())

    if not args.topic and not args.file:
        parser.print_help()
        print("\n [提示] 请至少指定 --topic 或 --file 参数。")
        sys.exit(1)

    print("=" * 50)
    print(" Weisse Wunderstern")
    print(" 零依赖轻量级智能体编排引擎")
    print("=" * 50)
    print()

    job_id = os.path.basename(args.output.rstrip("/\\"))

    try:
        run_job(job_id, topic=args.topic, file_path=args.file)
    except PipelineError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] 未预期的错误: {e}")
        sys.exit(2)
