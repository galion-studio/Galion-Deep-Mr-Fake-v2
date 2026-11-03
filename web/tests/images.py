"""Tiny synthetic images for tests. No checked-in fixtures."""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def solid_image(
    size: tuple[int, int] = (32, 24),
    color: tuple[int, int, int] = (180, 40, 40),
) -> Image.Image:
    return Image.new("RGB", size, color)


def image_bytes(
    fmt: str = "PNG",
    size: tuple[int, int] = (32, 24),
    color: tuple[int, int, int] = (180, 40, 40),
) -> bytes:
    buffer = BytesIO()
    solid_image(size, color).save(buffer, format=fmt)
    return buffer.getvalue()
