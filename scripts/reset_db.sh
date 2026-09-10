#!/bin/bash
# 重置数据库：先备份，再删除 SQLite 文件并按种子数据重新初始化
# （知识点恢复初始状态，学习记录与复习日志清空）。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from urania import config, db, seed
from urania.repository import KnowledgeRepository

backup = db.backup_database(config.DB_PATH)
if backup is not None:
    print(f"重置前已备份: {backup}")

if config.DB_PATH.exists():
    config.DB_PATH.unlink()
    print(f"已删除旧数据库: {config.DB_PATH}")

conn = db.init(config.DB_PATH)
n = seed.seed_if_needed(KnowledgeRepository(conn))
print(f"已按种子数据重新导入 {n} 个知识点。")
PY
