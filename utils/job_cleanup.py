"""任务清理工具 — 删除超过保留期的 job 目录。

用法：
  python utils/job_cleanup.py                    # 使用默认保留期（7天）
  python utils/job_cleanup.py --days 3           # 3天保留期
  python utils/job_cleanup.py --dry-run          # 预览但不删除

环境变量 JOB_RETENTION_DAYS 可设置默认保留天数。
"""

import os
import shutil
import time
from pathlib import Path

DEFAULT_RETENTION_DAYS = 7
JOBS_DIR = os.path.join("outputs", "jobs")


def cleanup_old_jobs(retention_days: int = None, dry_run: bool = False) -> tuple[int, int]:
    """
    删除超过保留期的 job 目录。

    返回 (deleted_count, total_scanned)。
    """
    if retention_days is None:
        retention_days = int(os.environ.get("JOB_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))

    if not os.path.isdir(JOBS_DIR):
        return 0, 0

    cutoff = time.time() - (retention_days * 86400)
    deleted = 0
    total = 0

    for entry in os.listdir(JOBS_DIR):
        job_path = os.path.join(JOBS_DIR, entry)
        if not os.path.isdir(job_path):
            continue
        total += 1
        try:
            mtime = os.path.getmtime(job_path)
            if mtime < cutoff:
                if dry_run:
                    print(f"[DRY-RUN] 将删除: {job_path} (mtime: {time.ctime(mtime)})")
                else:
                    shutil.rmtree(job_path)
                    print(f"[CLEAN] 已删除: {job_path}")
                deleted += 1
        except Exception as e:
            print(f"[ERROR] 无法处理 {job_path}: {e}")

    return deleted, total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="清理过期的 job 目录")
    parser.add_argument("--days", type=int, default=None, help="保留天数")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    deleted, total = cleanup_old_jobs(retention_days=args.days, dry_run=args.dry_run)

    if args.dry_run:
        print(f"预览完成: 将删除 {deleted}/{total} 个 job")
    else:
        print(f"清理完成: 删除 {deleted}/{total} 个 job，保留 {total - deleted} 个")
