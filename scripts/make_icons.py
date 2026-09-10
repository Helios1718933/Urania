#!/usr/bin/env python3
"""生成 Urania 的应用图标（纯标准库，不依赖 Pillow）。

用法:
    python3 scripts/make_icons.py

输出（frontend/assets/）:
    icon-192.png            PWA 图标
    icon-512.png            PWA 图标（大）
    apple-touch-icon.png    180×180，iOS/HarmonyOS 添加到桌面用

设计：圆角方块 + 系统蓝渐变 + 白色 U 字形。
四点取样做抗锯齿；图形保持在中心 60% 的安全区内，便于被系统裁成圆形。
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "assets"

BG_TOP = (10, 132, 255)      # systemBlue
BG_BOTTOM = (0, 78, 190)
GLOW = (90, 170, 255)

# U 字形几何（归一化坐标）
CX, CY = 0.5, 0.475
R_OUT, R_IN = 0.200, 0.115
ARM_TOP = 0.325
SUPERSAMPLE = 3


def _rounded_square_alpha(x: float, y: float, n: float = 4.0) -> float:
    """超椭圆内为 1，外为 0（n=4 接近 iOS 圆角方形）。"""
    dx = abs(x - 0.5) / 0.5
    dy = abs(y - 0.5) / 0.5
    return 1.0 if (dx ** n + dy ** n) <= 1.0 else 0.0


def _in_u(x: float, y: float) -> bool:
    dx, dy = x - CX, y - CY
    r = math.hypot(dx, dy)
    if dy >= 0:                                  # 下半：圆环
        return R_IN <= r <= R_OUT
    return (R_IN <= abs(dx) <= R_OUT) and (y >= ARM_TOP)   # 上半：两根竖笔


def _blend(base: tuple, overlay: tuple, alpha: float) -> tuple:
    return tuple(int(round(b * (1 - alpha) + o * alpha)) for b, o in zip(base, overlay))


def _pixel(x: float, y: float, pixel: float) -> tuple[int, int, int, int]:
    """返回某点颜色（4 通道）。

    Args:
        x, y: 归一化坐标（0~1），指向像素中心。
        pixel: 一个像素在归一化坐标下的宽度（1/size），用于超采样偏移。
    """
    # 子像素偏移：在「一个像素」范围内均匀取样
    offsets = [((i + 0.5) / SUPERSAMPLE - 0.5) * pixel for i in range(SUPERSAMPLE)]

    cov_bg = cov_u = cov_glow = 0.0
    samples = SUPERSAMPLE * SUPERSAMPLE
    for ox in offsets:
        for oy in offsets:
            sx, sy = x + ox, y + oy
            cov_bg += _rounded_square_alpha(sx, sy)
            if _in_u(sx, sy):
                cov_u += 1.0
            # 左上角柔光
            d = math.hypot(sx - 0.18, sy - 0.14)
            if d < 0.55:
                cov_glow += (1 - d / 0.55) ** 2
    cov_bg /= samples
    cov_u /= samples
    cov_glow /= samples

    if cov_bg <= 0:
        return (0, 0, 0, 0)

    # 渐变底色
    color = tuple(int(round(a + (b - a) * y)) for a, b in zip(BG_TOP, BG_BOTTOM))
    color = _blend(color, GLOW, min(0.35, cov_glow * 0.35))
    color = _blend(color, (255, 255, 255), cov_u)

    alpha = int(round(255 * cov_bg))
    return (color[0], color[1], color[2], alpha)


def _png_bytes(size: int) -> bytes:
    pixel = 1.0 / size
    rows = []
    for py in range(size):
        y = (py + 0.5) / size
        row = bytearray()
        for px in range(size):
            x = (px + 0.5) / size
            row.extend(_pixel(x, y, pixel))
        rows.append(bytes(row))
    return _encode_png(size, size, rows)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _encode_png(width: int, height: int, rows: list[bytes]) -> bytes:
    raw = b"".join(b"\x00" + row for row in rows)   # 每行前缀 filter 类型 0
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = {
        "icon-192.png": 192,
        "icon-512.png": 512,
        "apple-touch-icon.png": 180,
    }
    for name, size in targets.items():
        data = _png_bytes(size)
        path = OUT_DIR / name
        path.write_bytes(data)
        print(f"✅ {path.relative_to(OUT_DIR.parent.parent)}  ({size}×{size}, {len(data) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
