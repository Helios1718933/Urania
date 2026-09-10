#!/usr/bin/env python3
"""把 Mnemosyne 知识库导入 Urania 数据库。

用法:
    python3 scripts/import_mnemosyne.py --dry-run    # 预览会发生什么（不改库）
    python3 scripts/import_mnemosyne.py              # 正式导入（会先自动备份）

流程:
    1. 备份当前数据库（VACUUM INTO data/backups/）
    2. 按 RENAMES 把旧条目改名，对齐 Mnemosyne 的规范名称
       —— 学习记录挂在 point_id 上，改名不会丢进度
    3. 按名称 upsert：已存在则更新内容，不存在则新增
    4. 打印统计，并校验学习记录与复习日志数量未变

字段映射（Mnemosyne → Urania）:
    name           → name
    module_name    → category（保留路线图的模块结构）
    definition     → principle（兼容只读 principle 的旧渲染路径）
    definition/mechanism/key_point/code_example → 同名字段（四段式）
    visualization / tags / difficulty / source / self_test / module / stage → 同名字段

知识库位置默认取 ~/Desktop/Gaia/Mnemosyne，可用环境变量 URANIA_MNEMOSYNE 覆盖。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from urania import config, db  # noqa: E402
from urania.repository import KnowledgeRepository  # noqa: E402

DEFAULT_MNEMOSYNE = Path.home() / "Desktop" / "Gaia" / "Mnemosyne"

# 旧条目的名字 → Mnemosyne 的规范名字。
# 不改名会与导入内容重复（同一知识点存两遍），而且学习记录会对不上。
RENAMES: dict[str, str] = {
    "列表推导式": "列表推导式 List Comprehension",
    "装饰器": "装饰器 Decorator",
    "生成器与 yield": "生成器 Generator",
    "上下文管理器与 with": "上下文管理器 Context Manager",
    "GIL 全局解释器锁": "全局解释器锁 GIL",
    "浅拷贝与深拷贝": "浅拷贝与深拷贝 Shallow vs Deep Copy",
    "可变与不可变类型": "可变与不可变类型 Mutable vs Immutable",
    "asyncio 与事件循环": "事件循环 Event Loop",
    "闭包与 LEGB 作用域": "闭包 Closure",
    "元类 metaclass": "元类 Metaclass",
    "描述符协议": "描述符 Descriptor",
    "__slots__ 与实例字典": "实例字典与 __slots__",
    "multiprocessing 多进程": "多进程 Multiprocessing",
    "梯度下降": "梯度下降 Gradient Descent",
    "过拟合与正则化": "过拟合与正则化 Overfitting and Regularization",
    "偏差-方差权衡": "偏差方差权衡 Bias-Variance Tradeoff",
    "交叉验证": "交叉验证 Cross Validation",
    "特征工程": "特征工程 Feature Engineering",
    "集成学习：Bagging 与 Boosting": "集成学习 Ensemble Learning",
    "朴素贝叶斯": "朴素贝叶斯 Naive Bayes",
    "反向传播": "反向传播 Backpropagation",
    "CNN 卷积神经网络": "卷积神经网络 CNN",
    "Transformer 与自注意力": "自注意力 Self-Attention",
    "词向量与 Word2Vec": "词向量 Word2Vec",
    "批归一化 BatchNorm": "批归一化 BatchNorm",
    "交叉熵损失": "交叉熵损失 Cross Entropy Loss",
    "SQL 索引原理": "索引原理 B-Tree Index",
    "RESTful API 设计": "RESTful API 设计 RESTful Design",
    "Git 分支工作流": "分支工作流 Git Branching",
    "Docker 镜像与容器": "镜像与容器 Image and Container",
    "协程与生成器的关系": "协程与 async await Coroutine",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入 Mnemosyne 知识库")
    parser.add_argument(
        "--source", type=Path,
        default=Path(__import__("os").environ.get("URANIA_MNEMOSYNE", DEFAULT_MNEMOSYNE)),
        help="Mnemosyne 目录（默认 ~/Desktop/Gaia/Mnemosyne）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写库")
    parser.add_argument("--no-backup", action="store_true", help="跳过导入前备份")
    return parser.parse_args()


def load_items(source: Path) -> list[dict]:
    """读取 Mnemosyne 全部模块文件，转成 Urania 的字段结构。"""
    files = sorted(source.glob("S1/*.json")) + sorted(source.glob("S2/*.json"))
    if not files:
        raise SystemExit(f"❌ 在 {source} 下没找到 S1/*.json 或 S2/*.json")

    items: list[dict] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        module_name = data["module_name"]
        for it in data["items"]:
            items.append({
                "name": it["name"],
                "category": module_name,
                # principle 存一句话定义：让只认 principle 的旧渲染路径也有内容
                "principle": it.get("definition", ""),
                "visualization": it.get("visualization", ""),
                "tags": it.get("tags", []),
                "definition": it.get("definition", ""),
                "mechanism": it.get("mechanism", ""),
                "key_point": it.get("key_point", ""),
                "code_example": it.get("code_example", ""),
                "source": it.get("source", ""),
                "self_test": it.get("self_test", ""),
                "module": it.get("module", ""),
                "stage": it.get("stage", 1),
                "difficulty": it.get("difficulty", 0),
            })
    return items


def main() -> int:
    args = parse_args()
    source: Path = args.source

    if not source.is_dir():
        raise SystemExit(f"❌ 知识库目录不存在: {source}")

    items = load_items(source)
    names = {it["name"] for it in items}
    print(f"📚 从 {source} 读到 {len(items)} 条知识点\n")

    # 先校验改名目标都存在，避免改完名却匹配不上
    unknown = sorted({new for old, new in RENAMES.items() if new not in names})
    if unknown:
        raise SystemExit(
            "❌ 以下改名目标在知识库里不存在，请检查 RENAMES：\n  - "
            + "\n  - ".join(unknown)
        )

    conn = db.init(config.DB_PATH)
    repo = KnowledgeRepository(conn)

    points_before = len(repo.list_points())
    records_before = len(repo.learned_with_records())
    logs_before = repo.review_log_count()
    print(f"📊 导入前：知识点 {points_before} 条、学习记录 {records_before} 条、"
          f"复习日志 {logs_before} 条\n")

    if args.dry_run:
        existing = {p.name for p in repo.list_points()}
        will_rename = sum(1 for old in RENAMES if old in existing)
        will_update = sum(1 for name in names if name in existing or name in RENAMES.values())
        print("🔍 预览模式（不写库）：")
        print(f"   改名 {will_rename} 条（旧名 → 规范名）")
        print(f"   更新 {will_update} 条、新增 {len(names) - will_update} 条")
        print(f"   完成后预计共 {len(names)} 条")
        conn.close()
        return 0

    if not args.no_backup:
        backup = db.backup_database(config.DB_PATH, config.BACKUP_DIR)
        if backup:
            print(f"🛡  已备份到 {backup}\n")

    # 1) 改名对齐
    renamed = 0
    for old, new in RENAMES.items():
        if repo.rename_point(old, new):
            renamed += 1
    print(f"✏️  改名 {renamed} 条")

    # 2) 导入/更新
    stats = repo.upsert_points(items)
    print(f"📥 新增 {stats['inserted']} 条、更新 {stats['updated']} 条、"
          f"无变化 {stats['unchanged']} 条")

    # 3) 校验
    points_after = len(repo.list_points())
    records_after = len(repo.learned_with_records())
    logs_after = repo.review_log_count()
    print(f"\n📊 导入后：知识点 {points_after} 条、学习记录 {records_after} 条、"
          f"复习日志 {logs_after} 条")

    ok = True
    if records_after != records_before:
        print(f"⚠️  学习记录数量变化（{records_before} → {records_after}）")
        ok = False
    if logs_after != logs_before:
        print(f"⚠️  复习日志数量变化（{logs_before} → {logs_after}）")
        ok = False
    # 知识点总数应等于知识库条目数：多出来通常意味着库里有同义旧条目未对齐
    if points_after != len(items):
        print(f"⚠️  知识点总数 {points_after} 与知识库条目数 {len(items)} 不一致，"
              f"可能残留了未对齐的旧条目（旧名未列入 RENAMES）")
        ok = False
    if records_after:
        sample = repo.learned_with_records()[0][0]
        print(f"   抽查：{sample.name}（掌握度记录仍在）")

    conn.close()
    if ok:
        print("\n✅ 导入完成，学习进度未受影响")
        return 0
    print("\n⚠️  导入完成，但校验未通过，请检查（备份文件可用于回滚）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
