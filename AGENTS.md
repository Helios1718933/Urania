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
python3 main.py --no-window               # 只起服务，不开窗口（CI/调试）
python3 main.py --reset                   # 重置数据库重新播种
python3 -m unittest discover -s tests -v  # 跑全部测试（改代码后必须全绿）
./scripts/reset_db.sh                     # 重置数据库（脚本版）
./scripts/make_app.sh                     # 重新生成 dist/Urania.app
```

服务健康检查：`curl http://127.0.0.1:8765/api/health`。

## 架构速记（详见 docs/ARCHITECTURE.md）

- 分层：`api.py`（路由）→ `repository.py`（唯一写 SQL 处）→ `db/models`（SQLite）；核心算法在 `sampler.py`（随机抽取）与 `review.py`（自评→掌握度/间隔），二者是纯函数，随机源可注入。
- 「未标注」= `learning_records` 中无对应行；抽取不改变状态。
- 状态机：unlearned → learning（标记，mastery 1~3）→ mastered（mastery ≥ 4）；删记录可回到 unlearned。
- 自评：forgot(−1,1天) / fuzzy(不变) / solid(+1)，间隔表 {1:1, 2:2, 3:5, 4:8, 5:15} 天。
- 前端零框架零构建；所有服务端数据插值必须经 `app.js` 的 `esc()`。

## 代码约定

- Python：标准库优先；类型注解齐全；docstring 用中文；模块级常量大写。
- 错误处理：业务错误抛 `RepositoryError`（api 层转 400/404），不裸 `except`。
- 测试：unittest（不用 pytest）；`tests/common.py` 提供临时数据库夹具；API 测试用随机端口起真实服务。
- 文案/UI：中文界面、macOS 系统色板与控件尺寸；颜色一律走 CSS 设计令牌（`--blue` 等），深浅色自动适配必须保持。

## 改动后的验收清单

1. `python3 -m unittest discover -s tests` 全绿；
2. `./run.sh` 启动后依次人工检查：抽取 → 标记学习 → 复习自评 → 统计数字变化；
3. 深色模式下 UI 无错乱（可在系统设置切换外观，或浏览器开发者工具模拟）；
4. 不破坏「项目位于桌面 Gaia/Urania」的结构；运行时数据（`data/*.db`）不入 git。

## 未完成的候选方向（Roadmap）

知识点编辑/删除界面、复习会话模式、批量导入导出、分类加权抽取、py2app 正式打包。
