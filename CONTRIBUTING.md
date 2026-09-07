# 贡献指南

感谢关注 Urania！这是一台 Mac 上的个人学习小工具，欢迎 issue 与 PR。

## 开发环境

- macOS 11+，Python 3.10+（无需任何第三方依赖）
- 可选：`pip install pywebview pyobjc`（原生窗口形态）

```bash
git clone <你的 fork>
cd Urania
./run.sh                                  # 启动
python3 -m unittest discover -s tests -v  # 测试
```

## 提交规范

- 分支命名：`feat/xxx`、`fix/xxx`、`docs/xxx`
- Commit message：一行英文或中文祈使句，说清「做了什么」（如 `fix: 复习队列排序忽略时间部分`）
- 每个 PR 聚焦一件事；UI 改动请附截图（浅色 + 深色各一张）

## 代码约定

- 核心算法保持纯函数（`sampler.py` / `review.py`），不引入 I/O 与全局状态
- SQL 只写在 `repository.py`；API 层不写 SQL
- 前端零框架、零构建链；服务端数据插值必须经 `esc()` 转义
- 界面文案中文，样式使用 `styles.css` 中的设计令牌，保持深浅色模式兼容
- 改动行为时同步更新 `docs/ARCHITECTURE.md` / `docs/API.md` 与 `CHANGELOG.md`

## 测试要求

所有 PR 必须保证：

```bash
python3 -m unittest discover -s tests
```

全绿；新增功能需附带对应测试（算法层 / 仓库层 / API 层至少其一）。
