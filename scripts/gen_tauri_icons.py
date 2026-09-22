# -*- coding: utf-8 -*-
"""从 PWA 图标派生 Tauri 桌面图标（icon.ico + PNG 多尺寸）。

用法:
    python scripts/gen_tauri_icons.py
输入: docs/public/icons/icon-512.png
输出: src-tauri/icons/{icon.ico, 32x32.png, 128x128.png, 128x128@2x.png}
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "public" / "icons" / "icon-512.png"
OUT = ROOT / "src-tauri" / "icons"

# Tauri Windows 端需要的尺寸
PNG_SIZES = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
}
# icon.ico 内嵌多尺寸，资源管理器各视图都清晰
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"缺少源图标: {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)

    img = Image.open(SRC).convert("RGBA")

    for name, size in PNG_SIZES.items():
        img.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print(f"[ok] {name} ({size}x{size})")

    # 注意：Pillow 的 ICO 插件只从原图「缩小」生成各尺寸（不会放大），
    # 所以基底必须是 512 原图，不能是缩小后的 16x16
    img.save(
        OUT / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
    )
    print(f"[ok] icon.ico ({', '.join(str(s) for s in ICO_SIZES)})")


if __name__ == "__main__":
    main()
