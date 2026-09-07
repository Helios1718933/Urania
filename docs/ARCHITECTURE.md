# 架构与设计文档

本文档面向后续维护者（包括 AI agent），解释 Urania 的分层设计、领域规则与关键取舍。

## 1. 总体架构

```
┌────────────────────────────────────────────────────┐
│  frontend/（原生 JS + CSS，Apple HIG 风格）          │
│  抽取视图 · 复习视图 · 统计视图                      │
└──────────────▲─────────────────────▲───────────────┘
               │ 静态文件 /static      │ fetch /api/*
┌──────────────┴─────────────────────┴───────────────┐
│  urania.api（标准库 http.server，仅监听 127.0.0.1）  │
│  路由 → 参数校验 → Repository → JSON                 │
├────────────────────────────────────────────────────┤
│  核心功能层（纯 Python，可独立测试）                  │
│  sampler.py  随机抽取未标注知识点                    │
│  review.py   自评三档 → 掌握度/间隔更新（SRS-lite）  │
├────────────────────────────────────────────────────┤
│  repository.py（唯一允许写 SQL 的地方）              │
├────────────────────────────────────────────────────┤
│  db.py + models.py + seed.py（SQLite / 数据模型）   │
└────────────────────────────────────────────────────┘
```

分层规则（改动时请遵守）：

- `sampler.py` / `review.py` 是**纯函数层**，不 import sqlite3、不做 I/O，随机源通过 `rng` 参数注入便于测试。
- SQL 只出现在 `repository.py`；API 层不写 SQL，只调用仓库方法。
- `api.py` 只做路由、JSON 编解码与错误码转换（`RepositoryError` → 400/404，其余 → 500）。
- 前端不依赖任何框架与构建工具；`app.js` 中所有服务端数据的插值必须经过 `esc()` 转义。

## 2. 数据模型

```
knowledge_points                     learning_records
─────────────────────                ─────────────────────────
id            PK                     id           PK
name          UNIQUE NOT NULL        point_id     UNIQUE FK → knowledge_points.id
category      NOT NULL               status       learning | mastered
principle     NOT NULL               mastery      1~5
visualization TEXT                   review_count INTEGER
tags          CSV TEXT               last_reviewed_at ISO 时间
created_at / updated_at              next_review_at  YYYY-MM-DD（用于到期判断）
```

- **「未标注」的定义**：`knowledge_points` 中没有对应 `learning_records` 行。抽取查询用 `LEFT JOIN ... WHERE r.id IS NULL`。
- 一对一关系（`point_id UNIQUE`）：一个知识点最多一条学习记录，学习状态内联在记录上而不是知识点上。
- `seed.py` 按名称幂等导入：种子文件里已有条目不会被覆盖，用户的学习记录永远优先。

## 3. 领域规则（状态机与算法）

### 3.1 状态机

```
            mark_learned(mastery 1~3)
 unlearned ────────────────────────────▶ learning
                                            │ apply_rating(solid) 且 mastery ≥ 4
                                            ▼
                                         mastered
                                            │ apply_rating(forgot) 且 mastery < 4
                                            ▼
                                         learning
 （任意已学习状态）─ delete record ──▶ unlearned
```

### 3.2 自评算法（review.py）

| 自评 | mastery | 下次间隔 |
|------|---------|----------|
| forgot 忘了 | −1（下限 1） | 1 天 |
| fuzzy 有点模糊 | 不变 | 当前 mastery 对应间隔 |
| solid 记住了 | +1（上限 5） | 新 mastery 对应间隔 |

间隔表 `{1:1, 2:2, 3:5, 4:8, 5:15}` 天。mastery ≥ 4 时 status 置为 mastered，但仍保留在复习队列中巩固。要调整算法只需改 `BASE_INTERVAL_DAYS` 与 `apply_rating`，测试在 `tests/test_review.py`。

### 3.3 复习队列排序

`next_review_at` 升序，到期（≤ 今天）的排最前并标记 `is_due`；同日按 mastery 升序（先巩固弱的）。

## 4. 关键取舍

- **为什么标准库而不是 Flask/FastAPI**：交付目标是一台「拿到就能跑」的 Mac；零依赖意味着没有 pip、没有虚拟环境、没有版本冲突。接口层很薄，替换成框架的成本也低。
- **为什么 SQLite**：内置数据库是需求；单文件、零配置、`ON CONFLICT` upsert 与外键足够支撑单用户规模。
- **为什么 Web 视图而不是纯 AppKit**：Python 实现「核心功能代码」是硬约束，AppKit 需要 PyObjC 深度绑定；Web 视图（pywebview / 浏览器）+ HIG 风格 CSS 是维护性与观感的平衡点。若未来想换 SwiftUI，可以保留 `urania/` 全部核心代码，只替换 frontend 与窗口壳（API 契约见 docs/API.md）。
- **`_STATIC_TYPES` 白名单**：静态服务只允许 frontend/ 下带已知后缀的文件，且 `resolve()` 后必须仍位于 frontend/ 内（防目录穿越，tests/test_api.py 有覆盖）。
- **端口冲突**：`main.py --port` 可换端口；`server_address[1]` 取实际绑定端口，传 0 时由系统分配（测试用它避免竞态）。

## 5. 如何加一个新功能（示范路径）

以「按分类过滤抽取」为例：

1. `repository.py`：`unlearned_points(category: str | None = None)`，SQL 加 `AND p.category = ?`。
2. `api.py`：`/api/draw` 读取 query 参数 `category` 并透传。
3. `frontend/js/app.js`：抽取视图加分类选择器，fetch 时带上参数。
4. `tests/`：为 `unlearned_points` 的过滤行为补用例；跑 `python3 -m unittest discover -s tests`。

## 6. 已知限制 / 后续方向

- `api.py` 的 `do_POST` 用正则逐段匹配，路由增多后可抽成小的路由表。
- `visualization` 存单个字符串（链接或文字），若要支持多链接需改列结构或约定分隔符。
- 打包脚本 `scripts/make_app.sh` 记录的是生成时的绝对路径，项目移动后需重新生成；正式分发建议改用 py2app。
- 并发模型是「每请求一线程 + SQLite 即时提交」，单用户没问题；多进程同时写同一 db 文件不在设计范围内。
