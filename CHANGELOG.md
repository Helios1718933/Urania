# Changelog

本项目的所有重要变更都记录在本文件中。
格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中
- 知识点编辑与删除界面
- 复习会话模式（按「今天该复习」批量过一遍）
- JSON / Markdown 批量导入导出
- 抽取按分类加权
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

[Unreleased]: https://github.com/helios/urania/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/helios/urania/releases/tag/v0.1.0
