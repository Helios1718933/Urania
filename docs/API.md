# REST API 参考

Base URL：`http://127.0.0.1:8765`（仅本机回环，端口可用 `--port` 修改）

所有响应为 JSON（`ensure_ascii=false`，中文原样输出）。错误响应形如 `{"error": "原因"}`。

## 系统

### `GET /api/health`
```json
{"status": "ok", "app": "Urania", "version": "0.1.0"}
```

### `GET /api/config`
前端领域常量：掌握度标签、状态标签、自评档位标签、默认分类列表。

## 核心功能

### `GET /api/draw`
随机抽取一个未标注（未学习）知识点。**不改变任何状态**，可反复调用。
```json
{
  "point": {
    "id": 9, "name": "闭包与 LEGB 作用域", "category": "Python 进阶",
    "principle": "内层函数引用外层函数的局部变量……",
    "visualization": "https://… 或 文字说明", "tags": ["函数式", "高频面试"],
    "status": "unlearned", "status_label": "未学习",
    "mastery": 0, "mastery_label": "未学习",
    "review_count": 0, "last_reviewed_at": null,
    "next_review_at": null, "is_due": false
  },
  "remaining": 26
}
```
全部知识点都进入学习循环时 `"point": null`。

## 知识点

### `GET /api/points`
全部知识点（含学习状态），`{"items": [ …同上结构… ]}`，按分类与 id 排序。

### `GET /api/points/{id}`
单个知识点，`{"point": …}`；不存在返回 404。

### `POST /api/points`
新增知识点，返回 201。重名返回 400。
```json
{"name": "起泡排序", "category": "算法", "principle": "……", "visualization": "https://…", "tags": ["排序"]}
```
`category` / `principle` / `visualization` / `tags` 均可省略。

## 学习循环

### `POST /api/points/{id}/learn`
把未学习知识点标记为已学习，产生学习记录。
```json
{"mastery": 2}
```
`mastery` 取 1~3（越界自动收敛），返回 `{"point": …}`。重复标记返回 400。

### `POST /api/points/{id}/review`
提交一次复习自评（仅对已有学习记录的知识点）。
```json
{"rating": "solid"}
```
`rating ∈ {forgot, fuzzy, solid}`；非法值 400，无学习记录 404。
返回更新后的 `{"point": …}`（含新的 mastery、status、next_review_at）。

### `DELETE /api/points/{id}/record`
删除学习记录，知识点回到「未标注 / 未学习」。`{"ok": true}`。

### `GET /api/review/queue`
复习队列：到期优先，其余按 next_review_at 升序、mastery 升序。
```json
{"items": [ …知识点视图… ], "today": "2026-09-07"}
```

## 统计

### `GET /api/stats`
```json
{
  "total": 31, "unlearned": 26, "learning": 5, "mastered": 0,
  "learned": 5, "due": 3, "total_reviews": 13,
  "mastery_distribution": {"1": 2, "2": 1, "3": 2, "4": 0, "5": 0}
}
```

## 静态页面

| 路径 | 说明 |
|------|------|
| `/` 或 `/index.html` | 应用页面 |
| `/css/*`、`/js/*` | 样式与脚本（白名单后缀，防目录穿越） |
