#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PWA 图标生成器（纯标准库，无 PIL 依赖）
生成 manifest 需要的 PNG 图标：192 / 512 / maskable-512。
设计与 docs/public/icon.svg 一致：靛蓝渐变圆角方块 + 白色「CL」字块。
"""

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "public" / "icons"

# 5x7 点阵字模（C 与 L）
GLYPH_C = [
    "01110",
    "10001",
    "10000",
    "10000",
    "10000",
    "10001",
    "01110",
]
GLYPH_L = [
    "10000",
    "10000",
    "10000",
    "10000",
    "10000",
    "10000",
    "11111",
]
GRID_W, GRID_H = 11, 7  # C(5) + 间隔(1) + L(5)


def inside_letter(u, v):
    """u,v ∈ [0,GRID_W/GRID_H)，以「格」为单位，是否落在 CL 字块内。"""
    col, row = int(u), int(v)
    if row < 0 or row >= GRID_H or col < 0 or col >= GRID_W:
        return False
    if col == 5:  # 间隔列
        return False
    g = GLYPH_C if col < 5 else GLYPH_L
    c = col if col < 5 else col - 6
    return g[row][c] == "1"


def rounded_alpha(x, y, size, radius):
    """圆角方块覆盖度（0 或 1）：只有四个角圆弧外的区域透明。"""
    if not (0 <= x < size and 0 <= y < size):
        return 0.0
    r = radius
    in_x_corner = x < r or x > size - r
    in_y_corner = y < r or y > size - r
    if not (in_x_corner and in_y_corner):
        return 1.0
    ax = r if x < r else size - r
    ay = r if y < r else size - r
    return 1.0 if (x - ax) ** 2 + (y - ay) ** 2 <= r * r else 0.0


def make_icon(size, letter_scale, out_path):
    radius = round(size * 112 / 512)
    pad = size * 0.06  # 字块在圆角内再留边
    box = size - 2 * pad
    letter_h = box * letter_scale
    cell = letter_h / GRID_H
    lw = cell * GRID_W
    ox = (size - lw) / 2
    oy = (size - letter_h) / 2

    # 渐变端色（靛蓝）
    c1 = (99, 102, 241)
    c2 = (79, 70, 229)

    rows = []
    ss = 3  # 字块 3x3 超采样
    for y in range(size):
        row = bytearray([0])  # filter type 0
        for x in range(size):
            a = rounded_alpha(x + 0.5, y + 0.5, size, radius)
            if a <= 0:
                row += bytes((0, 0, 0, 0))
                continue
            t = (x + y) / (2.0 * (size - 1))
            r = round(c1[0] + (c2[0] - c1[0]) * t)
            g = round(c1[1] + (c2[1] - c1[1]) * t)
            b = round(c1[2] + (c2[2] - c1[2]) * t)
            # 字块判定（超采样）
            hit = 0
            for sy in range(ss):
                for sx in range(ss):
                    px = (x + (sx + 0.5) / ss - ox) / cell
                    py = (y + (sy + 0.5) / ss - oy) / cell
                    if 0 <= px < GRID_W and 0 <= py < GRID_H and inside_letter(px, py):
                        hit += 1
            if hit:
                cov = hit / (ss * ss)
                r = round(r + (255 - r) * cov)
                g = round(g + (255 - g) * cov)
                b = round(b + (255 - b) * cov)
            row += bytes((r, g, b, 255))
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    out_path.write_bytes(png)
    print(f"wrote {out_path.name} ({out_path.stat().st_size} bytes)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make_icon(192, 0.62, OUT / "icon-192.png")
    make_icon(512, 0.62, OUT / "icon-512.png")
    make_icon(512, 0.45, OUT / "icon-512-maskable.png")  # 遮罩安全区：字块缩小


if __name__ == "__main__":
    main()
