# AGENTS.md · AI Agent 交接说明

> 本文件写给在本项目上工作的 AI agent（或新加入的人类开发者）。
> 目标：让任何人/agent 在不依赖原始对话上下文的情况下，安全地继续迭代本项目。

## 项目一句话

macOS 上的知识点随机抽取学习应用（Urania）：从内置 SQLite 中随机抽一个「未标注」的 Python/AI 知识点，展示名称+原理讲解+可视化链接；标记学习后进入掌握度复习循环。核心功能纯 Python 标准库实现，前端为 Apple HIG 风格本地 Web 界面。

## 当前状态（截至 2026-09-07）

- ✅ 已完成并可运行：抽取 / 标记学习 / 复习自评 / 统计三视图、内置种子数据（31 条占位）、37 个单元测试全部通过、API 与 UI 均经真机验证。
- 📌 需求硬约束（来自用户，勿违反）：
  1. 核心功能代码由 **Python** 实现；
  2. UI 遵循 **Apple 设计规范**；
  3. 主界面进入即「抽取新知识」，复习入口需体现**掌握程度**；
  4. 软件本体**内置小数据库**（目前不填充真实数据，`data/seed_knowledge.json` 为示例占位）；
  5. 项目必须位于 `~/Desktop/Gaia/Urania`。

## 常用命令

```bash
cd ~/Desktop/Gaia/Urania
./run.sh                                  # 启动（默认端口 8765，自动开窗口）
python3 main.py --lan                     # 局域网模式：手机可访问，需口令
python3 main.py --no-window               # 只起服务，不开窗口（CI/调试）
python3 main.py --reset                   # 重置数据库重新播种（会先自动备份）
python3 -m unittest discover -s tests -v  # 跑全部测试（改代码后必须全绿）
./scripts/reset_db.sh                     # 重置数据库（脚本版，同样先备份）
./scripts/backup_db.sh                    # 手动备份数据库
./scripts/make_icons.py                   # 生成 PWA 图标与 .icns
python3 scripts/import_mnemosyne.py --dry-run  # 预览知识库导入
python3 scripts/import_mnemosyne.py            # 从 Mnemosyne 导入知识点（先自动备份）
./scripts/make_app.sh                     # 生成自包含 dist/Urania.app（内嵌 Python）
./scripts/make_dmg.sh                     # 生成 dist/Urania_<版本>.dmg 安装包
```

**路径约定（打包相关改动务必遵守）**
- 只读资源（`frontend/`、种子数据）走 `config.RESOURCE_ROOT`：源码运行时是项目根目录，
  打包后是 bundle 的 `Contents/Resources`（py2app 设置 `RESOURCEPATH`）。
- 可写数据（数据库/备份/令牌/锁）走 `config.DATA_DIR` =
  `~/Library/Application Support/Urania`。**不要把任何可写文件放回项目目录**，
  否则装进 /Applications 后写不进去。
- 旧版放在项目 `data/` 下的数据由 `db.migrate_legacy_data()` 在启动时自动搬迁（幂等）。

单实例机制：`data/urania.lock` 文件锁（flock）是权威判定，锁内写入运行实例端口；
网络探测（强制直连不走代理）仅作兜底。macOS 上 SO_REUSEADDR 允许重复绑定端口，
所以不能依赖「绑定失败」来发现占用。

服务健康检查：`curl http://127.0.0.1:8765/api/health`。
全量数据导出：`curl http://127.0.0.1:8765/api/export`。

## 数据库与迁移（改 schema 前必读）

- **版本管理**：`PRAGMA user_version` 是唯一事实来源；`schema_migrations` 表只作审计日志。
  `urania/migrations.py` 的 `MIGRATIONS` 是有序列表，启动时自动补齐。
- **迁移前自动备份**：`db.init()` 发现待应用迁移时先 `VACUUM INTO data/backups/`；新建库不备份。
- **写迁移的三条纪律**：
  1. 迁移函数只做 DDL/DML，用 `conn.execute()` 逐条执行——**不要用 `executescript()`**（它会隐式提交，破坏事务性）；
  2. 追加到 `MIGRATIONS` 末尾，版本号连续递增，然后补测试到 `tests/test_migrations.py`；
  3. 改完在真实库上验证：`python3 -c "from urania import config, db; db.init(config.DB_PATH).close()"`，确认数据量与备份文件。
- **表的分工**：`learning_records` = 当前状态（可覆盖）；`review_logs` = 历史事件（只追加，
  外键指向知识点，所以重置学习记录不会抹掉历史）。改调度/统计逻辑时不要绕过日志写入。

## 架构速记（详见 docs/ARCHITECTURE.md）

- 分层：`api.py`（路由）→ `repository.py`（唯一写 SQL 处）→ `db/migrations/models`（SQLite）；核心算法在 `sampler.py`（随机抽取）与 `review.py`（自评→掌握度/间隔），二者是纯函数，随机源可注入。
- `repository.apply_review()` 在**同一事务**内完成「读 → 算（调 review.apply_rating）→ 写记录 + 写日志」，不要拆回去分步调用。
- 「未标注」= `learning_records` 中无对应行；抽取不改变状态。
- 状态机：unlearned → learning（标记，mastery 1~3）→ mastered（mastery ≥ 4）；删记录可回到 unlearned。
- 自评：forgot(−1,1天) / fuzzy(不变) / solid(+1)，间隔表 {1:1, 2:2, 3:5, 4:8, 5:15} 天。
- 前端零框架零构建；所有服务端数据插值必须经 `app.js` 的 `esc()`。

## 代码约定

- Python：标准库优先；类型注解齐全；docstring 用中文；模块级常量大写。
- 错误处理：业务错误抛 `RepositoryError`（api 层转 400/404），不裸 `except`。
- 播种语义：`seed.seed_if_needed()` **只在知识库为空时**导入内置种子，不做「按名称补齐」——否则用户重命名或导入过的条目会在每次启动时被旧名字重新插回来（踩过一次）。
- 知识点字段：`principle` 是「一整段讲解」的旧字段；`definition/mechanism/key_point/code_example` 是四段式结构。前端 `structuredBlock()` 在结构化字段为空时回退到 principle。改渲染时两条路径都要照顾。
- 测试：unittest（不用 pytest）；`tests/common.py` 提供临时数据库夹具；API 测试用随机端口起真实服务。当前 114 个用例、覆盖率约 93%（门禁 85%）。
- 工具链：`ruff check .`（配置见 `pyproject.toml`，中文标点相关的 RUF001/002/003 已关）与 `mypy` 必须全绿；CI 有独立的 lint 作业。
- 时区：本项目刻意用本地时间（`date.today()` / `datetime.now()`），ruff 的 DTZ 规则已关闭，勿"修正"。
- 文案/UI：中文界面、macOS 系统色板与控件尺寸；颜色一律走 CSS 设计令牌（`--blue` 等），深浅色自动适配必须保持。

## 改动后的验收清单

1. `python3 -m unittest discover -s tests` 全绿；
2. `./run.sh` 启动后依次人工检查：抽取 → 标记学习 → 复习自评 → 统计数字变化；
3. 深色模式下 UI 无错乱（可在系统设置切换外观，或浏览器开发者工具模拟）；
4. 不破坏「项目位于桌面 Gaia/Urania」的结构；运行时数据（`data/*.db`）不入 git。

## 未完成的候选方向（Roadmap）

知识点编辑/删除界面、复习会话模式、批量导入导出、分类加权抽取、py2app 正式打包。
