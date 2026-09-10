# Changelog

本项目的所有重要变更都记录在本文件中。
格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- **自包含安装包**：`./scripts/make_app.sh` 用 py2app 生成内嵌 Python 运行时的
  `dist/Urania.app`（55MB，通用二进制），目标 Mac 无需预装 Python；`make_dmg.sh`
  生成 29MB 的 DMG。含 ad-hoc 签名与图标（`scripts/make_icons.py` 纯标准库生成
  PNG 与 .icns）
- **数据目录迁移**：用户数据从项目内 `data/` 迁到
  `~/Library/Application Support/Urania/`（macOS 规范位置，装进 /Applications 后仍可写）；
  旧数据首次启动自动搬迁（`db.migrate_legacy_data()`，幂等、不覆盖新数据）
- **手机端（鸿蒙浏览器）**：`--lan` 局域网模式 + 8 位访问口令（HttpOnly Cookie /
  Bearer 双通道）；PWA manifest + 图标，「添加到桌面」有独立图标
- **无障碍适配**：`prefers-reduced-transparency`（玻璃层降级为不透明）、
  `prefers-contrast: more`、`prefers-reduced-motion`；触控目标补齐到 44×44；
  刘海屏安全区
- 内联 SVG 图标（`frontend/js/icons.js`）替换 emoji（规范列为反模式）
- **`review_logs` 复习日志表**（只追加，对标 Anki 的 revlog）：`learning_records` 存「当前状态」、
  `review_logs` 存「历史事件」，两者分离后才能统计遗忘曲线与真实保留率。
  「标记学习」与「复习自评」都会追加一条日志（含评档、前后掌握度、间隔天数）
- **架构迁移机制**（`urania/migrations.py`）：以 `PRAGMA user_version` 为版本事实来源、
  `schema_migrations` 表作审计；启动时自动应用未执行的迁移，**迁移前自动 `VACUUM INTO` 备份**
- **数据导出**：`GET /api/export` 导出全库（知识点 + 学习记录 + 复习日志 + 元信息）
- **备份脚本** `scripts/backup_db.sh`；`--reset` 与 `scripts/reset_db.sh` 删库前自动备份
- 抽取页「回忆门」：抽到知识点先只显示名称，原理讲解与可视化模糊隐藏，
  2 分钟倒计时（右上角，最后 10s 变红脉动）或点「跳过」/按空格揭晓；
  正文模糊平滑退去，无矩形遮罩的零边界视觉
- 揭晓后三档自评「不知道 / 有点模糊 / 知道了」替代原「标记为已学习→选档」两步，
  一键映射初始掌握度（1 初识 / 2 理解 / 3 熟悉）
- `scripts/make_dmg.sh`：生成标准 macOS 安装包 `dist/Urania_<版本>.dmg`（拖入 Applications 即装）
- `.app` 启动器加固：双击运行日志落盘 `dist/Urania-run.log`；缺 python3 时弹窗提示而非静默失败

### Fixed
- **复习的读-改-写不再有丢更新风险**：原先「读取记录 → 计算 → 保存」分三步且无事务，
  并发请求会互相覆盖；现收敛为 `repository.apply_review()` 在**同一事务**内完成
  「读 → 算 → 写记录 + 写日志」
- `urania/server.py`：`port=0`（测试随机端口）被 `port or DEFAULT_PORT` 误替换为默认 8765，
  端口被占用时 API 测试全部失败；改为 `port if port is not None else ...`
- 单实例机制：反复双击 `.app` 会起多个服务（macOS SO_REUSEADDR 允许重复绑定端口，
  且健康探测在代理环境下访问 127.0.0.1 失效）。改为 `data/urania.lock` 文件锁（flock）
  作为权威判定，锁内写入运行实例端口；第二个进程读锁后只打开界面并退出

### Changed
- 分段控件（抽取新知识 / 复习 / 统计）升级为液态玻璃材质：胶囊形容器 + 选中态透镜
  （渐变填充、顶部高光、发丝描边、柔和投影），深浅色模式各自调参
- 回忆门浮层与倒计时、跳过按钮统一为同一份液态玻璃胶囊配方，不再以裸文字悬浮，
  并移除原文字描影方案；悬停跳过按钮时玻璃泛蓝
- 工具栏内部禁用嵌套 backdrop-filter（触发 Chromium 整条雾化bug），磨砂感直接继承工具栏

### 计划中
- 前端模块化拆分（`app.js` 单文件已 474 行）
- 局域网访问（手机端）+ 认证中间件
- 知识点编辑与删除界面
- 复习会话模式（按「今天该复习」批量过一遍）
- 统计升级：复习热力图、真实保留率、到期预测
- py2app 正式打包与签名

## [0.1.0] - 2026-09-07

### Added
- 核心功能：从未标注（未学习）知识点中随机抽取一个，展示名称、原理讲解与可视化链接
- 标记学习（初始掌握度 1~3 三档）与复习闭环：忘了 / 有点模糊 / 记住了 三档自评，
  自动更新掌握度并按 S-lite 间隔表（1/2/5/8/15 天）安排下次复习
- 复习队列视图：到期优先排序、掌握度圆点、今日应复习徽章
- 统计视图：进度环、未学习/学习中/已掌握/今日应复习计数、五档掌握度分布
- 内置 SQLite 小数据库（`data/urania.db`，运行时生成）与 31 条 Python/AI 示例种子数据（`data/seed_knowledge.json`）
- REST API（标准库 http.server，仅监听 127.0.0.1）与静态前端托管
- Apple HIG 风格界面：系统字体栈、macOS 系统色板、分段控件、毛玻璃工具栏、深浅色自动适配
- 可选 pywebview 原生窗口，未安装时自动回退浏览器；`scripts/make_app.sh` 生成可双击的 Urania.app
- 37 个单元测试（抽取均匀性/排除已学习、自评算法、数据仓库、API 端到端含目录穿越防护）
- GitHub Actions CI（macOS + Ubuntu × Python 3.10–3.13 测试矩阵）

[Unreleased]: https://github.com/Helios1718933/Urania/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Helios1718933/Urania/releases/tag/v0.1.0
