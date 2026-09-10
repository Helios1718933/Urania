#!/bin/bash
# 备份 Urania 数据库（VACUUM INTO 一致性快照，可对运行中的库安全执行）。
# 备份文件落在 data/backups/，文件名带时间戳，不会被覆盖。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from urania import config, db

path = db.backup_database(config.DB_PATH, config.BACKUP_DIR)
if path is None:
    print("数据库不存在或为空，无需备份。")
else:
    print(f"✅ 已备份到: {path}  ({path.stat().st_size / 1024:.1f} KB)")
PY
