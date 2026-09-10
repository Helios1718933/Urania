# Urania · 知识点点名册

一个运行在 macOS 上的原生质感小应用：**随机抽取内置数据库中一个「未标注（未学习）」的知识点**，帮你用随机的顺序攻克求职所需的 Python / AI 知识，并用掌握程度与间隔重复安排复习。

> 为什么叫 Urania？她是希腊神话中的天文缪斯，「属于天空的知识」。本项目是 Gaia 工作区的一员。

## ✨ 功能特性

- 🎲 **随机抽取 + 回忆门**：一键从未标注知识点随机抽一个，先只展示名称并**将原理讲解模糊隐藏**，进入 2 分钟回忆倒计时（右上角计时、可点「跳过」或按空格提前揭晓），逼你先主动回忆再揭晓，记忆更深
- 🏷 **标记学习（揭晓自评）**：揭晓后三档自评「不知道 / 有点模糊 / 知道了」替代手动选档，一键完成标记并映射初始掌握度（1 初识 / 2 理解 / 3 熟悉）
- 🔁 **复习闭环**：已学习知识点按掌握程度进入复习队列；凭记忆回想后三档自评（忘了 / 有点模糊 / 记住了），应用自动更新掌握度并安排下次复习时间（SRS-lite 间隔重复）
- 📊 **统计总览**：学习进度环、未学习 / 学习中 / 已掌握 / 今日应复习计数、五档掌握度分布
- 🍎 **Apple HIG 风格 UI**：系统字体栈（SF Pro / 苹方）、macOS 系统色板、分段控件、毛玻璃工具栏、深色 / 浅色模式自动适配
- 📚 **知识点四段式**：每条包含「定义 → 原理机制 → 面试/实战要点 → 可拷贝的代码例子」，并带难度、出处、自测关卡；由 `scripts/import_mnemosyne.py` 从 Mnemosyne 知识库导入（当前 369 条，覆盖转行路线图阶段①②）
- 💾 **内置小数据库**：SQLite 单文件（`data/urania.db`），首次启动自动建库并导入 31 个 Python / AI 示例知识点（`data/seed_knowledge.json`，占位数据，可自行替换）
- 📜 **复习历史可追溯**：`review_logs` 只追加表记录每一次标记与自评（评档、前后掌握度、间隔天数），为将来的遗忘曲线与保留率统计留数据
- 🛡 **数据安全**：`./scripts/backup_db.sh` 一键备份到 `data/backups/`；架构升级前自动备份；`--reset` 与重置脚本删库前也会先备份；`GET /api/export` 可导出全量 JSON
- 🐍 **核心功能纯 Python 实现**：随机抽取、复习调度、数据库、HTTP API 全部基于 Python 标准库（`sqlite3` / `http.server` / `random`），**零第三方依赖**
- 🖥 **两种窗口形态**：安装 `pywebview` 后以原生窗口运行；未安装则自动退回浏览器打开（界面观感一致）

## 🚀 快速开始

```bash
cd ~/Desktop/Gaia/Urania

# 方式一：一键启动（推荐）
./run.sh

# 方式二：直接运行
python3 main.py

# 常用参数
python3 main.py --browser     # 强制用浏览器打开（跳过原生窗口探测）
python3 main.py --port 9000   # 指定端口
python3 main.py --reset       # 重置数据库并重新播种
```

要求：macOS + Python 3.10+（系统自带或 [python.org](https://www.python.org/downloads/) 安装）。

想要**可双击运行的 App / 安装包**：

```bash
./scripts/make_app.sh         # 生成自包含的 dist/Urania.app（内嵌 Python）
./scripts/make_dmg.sh         # 生成 dist/Urania_<版本>.dmg 安装包（拖入 Applications 即装）
```

**自包含**：`.app` 内嵌 Python 运行时，目标 Mac **无需预装 Python**；把 `Urania.app`
拖进「应用程序」即可。首次打开若被 Gatekeeper 拦截（ad-hoc 签名），右键 → 打开。
对他人分发需要 Developer ID 签名 + 公证，本地自用不必。

**数据位置**：用户数据（数据库、复习历史、备份）放在
`~/Library/Application Support/Urania/`，不在应用包内——这样装进 `/Applications`
后仍可写。旧版放在项目 `data/` 下的数据会在首次启动时自动搬过去。

**局域网 / 手机访问**：

```bash
python3 main.py --lan         # 监听 0.0.0.0，打印手机访问地址与访问口令
```
手机浏览器打开终端显示的地址 → 输入口令 → 可「添加到桌面」当作图标用。
默认（不加 `--lan`）仍只监听 127.0.0.1，无需口令。

> 重复启动会被自动识别：已有实例运行时，再次双击只会打开界面，不会起第二个服务。

想要**真正的原生窗口**（可选）：

```bash
pip install pywebview pyobjc  # 之后 ./run.sh 会自动以原生窗口启动
```

## 🗂 项目结构

```
Urania/
├── main.py                  # 应用入口（建库 → 起服务 → 开窗口）
├── run.sh                   # 一键启动脚本
├── urania/                  # Python 核心包（核心功能全部在此）
│   ├── config.py            #   路径 / 领域常量（掌握度档位、状态机）
│   ├── models.py            #   数据模型：KnowledgePoint / LearningRecord
│   ├── db.py                #   SQLite 连接与 schema
│   ├── sampler.py           #   ★ 核心功能：随机抽取未标注知识点
│   ├── review.py            #   复习调度：自评三档 → 掌握度/间隔更新
│   ├── repository.py        #   数据仓库层（SQL 只出现在这里）
│   ├── seed.py              #   内置种子数据导入（幂等）
│   ├── api.py               #   REST API + 静态文件服务
│   └── server.py            #   ThreadingHTTPServer 装配（仅监听 127.0.0.1）
├── frontend/                # Apple HIG 风格界面（原生 JS，无框架）
│   ├── index.html
│   ├── css/styles.css       #   设计令牌 / 深浅色自适应
│   └── js/app.js            #   抽取 / 复习 / 统计三视图逻辑
├── data/
│   ├── seed_knowledge.json  #   内置知识点（示例占位数据，可替换）
│   └── urania.db            #   运行时自动生成的 SQLite 数据库（不入库 git）
├── scripts/
│   ├── make_app.sh          #   生成可双击的 Urania.app
│   ├── make_dmg.sh          #   生成 Urania_<版本>.dmg 安装包
│   └── reset_db.sh          #   重置数据库
├── tests/                   # 37 个单元测试（unittest，覆盖核心功能与 API）
├── docs/
│   ├── ARCHITECTURE.md      # 架构与领域规则详解
│   └── API.md               # REST API 参考
├── AGENTS.md                # 给 AI agent 的项目交接说明
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
└── .github/workflows/ci.yml # GitHub Actions：macOS + Ubuntu 测试矩阵
```

## 🧠 领域规则（设计约定）

- **未标注 = 未学习**：知识点没有学习记录即为「未标注」，才会被随机抽取命中；抽取动作本身不改变状态
- **状态机**：`unlearned → learning（标记学习）→ mastered（掌握度 ≥ 4）`；删除学习记录可回到 `unlearned`
- **掌握度五档**：1 初识 · 听说过 ／ 2 理解 · 能复述 ／ 3 熟悉 · 能解释 ／ 4 掌握 · 能应用 ／ 5 精通 · 能讲解；标记学习时初始值仅允许 1~3
- **自评三档**：忘了（掌握度 −1、明天再复习）／ 有点模糊（不变、按当前档位间隔重约）／ 记住了（+1、按新档位更长间隔）
- **复习间隔表**：按掌握度 1→5 分别为 1 / 2 / 5 / 8 / 15 天

详细设计见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，接口定义见 [docs/API.md](docs/API.md)。

## 🧪 运行测试

```bash
python3 -m unittest discover -s tests -v
```

覆盖：随机抽取的均匀性 / 排除已学习、自评与间隔计算、数据仓库增删改查、HTTP API 端到端（含目录穿越防护）。

## 🗺 Roadmap

- [ ] 知识点的编辑与删除界面
- [ ] 按「今天该复习」直接开始一轮复习会话
- [ ] JSON / Markdown 批量导入导出
- [ ] 抽取时按分类加权（可配置重点类别）
- [ ] 图标与签名后的独立 .app（py2app 打包）

## 📄 License

[MIT](LICENSE)
