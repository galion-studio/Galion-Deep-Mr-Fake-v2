"""Unit tests for the CPU image helpers in web/app.py."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException
from PIL import Image

from app import EDIT_DEFAULTS, _apply_edits, _cpu_generate, _resolve_params
from images import solid_image


def _edit(img: Image.Image, **overrides: Any) -> Image.Image:
    params = dict(EDIT_DEFAULTS)
    if "filter_name" in overrides:
        params["filter"] = overrides.pop("filter_name")
    params.update(overrides)
    return _apply_edits(img, params)


def _low_contrast() -> Image.Image:
    img = solid_image((16, 16), (10, 40, 80))
    for y in range(8):
        for x in range(16):
            img.putpixel((x, y), (200, 180, 160))
    return img


def _channel_mean(img: Image.Image) -> float:
    pixels = list(img.getdata())
    return sum(sum(pixel) for pixel in pixels) / (len(pixels) * 3)


def test_apply_edits_noop_keeps_rgb_pixels() -> None:
    img = solid_image((6, 4), (12, 34, 56))
    out = _edit(img)
    assert out.mode == "RGB"
    assert out.size == img.size
    assert list(out.getdata()) == list(img.getdata())


def test_apply_edits_converts_rgba_to_rgb() -> None:
    img = Image.new("RGBA", (5, 5), (10, 20, 30, 128))
    out = _edit(img)
    assert out.mode == "RGB"
    assert out.size == (5, 5)


def test_apply_edits_crop() -> None:
    img = solid_image((40, 30), (9, 9, 9))
    out = _edit(img, crop="5,5,10,8")
    assert out.size == (10, 8)


def test_apply_edits_crop_strips_whitespace() -> None:
    img = solid_image((40, 30))
    out = _edit(img, crop=" 1, 2, 3, 4 ")
    assert out.size == (3, 4)


def test_apply_edits_crop_clamps_to_image_bounds() -> None:
    img = solid_image((40, 30))
    out = _edit(img, crop="-4,-3,10,10")
    assert out.size == (6, 7)


def test_apply_edits_ignores_invalid_or_empty_crop() -> None:
    img = solid_image((12, 9), (3, 3, 3))
    for crop in ("nope", "1,2,3", "1,2,x,4", "100,100,5,5", ""):
        out = _edit(img, crop=crop)
        assert out.size == img.size
        assert list(out.getdata()) == list(img.getdata())


def test_apply_edits_resize_max_width_preserves_aspect() -> None:
    img = solid_image((100, 40))
    out = _edit(img, max_width=50)
    assert out.size == (50, 20)


def test_apply_edits_skips_resize_when_already_small() -> None:
    img = solid_image((40, 20))
    assert _edit(img, max_width=80).size == (40, 20)
    assert _edit(img, max_width=40).size == (40, 20)
    assert _edit(img, max_width=0).size == (40, 20)


def test_apply_edits_crop_then_resize() -> None:
    img = solid_image((100, 80))
    out = _edit(img, crop="10,10,50,40", max_width=25)
    assert out.size == (25, 20)


def test_apply_edits_brightness_and_contrast() -> None:
    img = solid_image((8, 8), (100, 100, 100))
    for x in range(4):
        img.putpixel((x, 0), (170, 170, 170))

    brighter = _edit(img, brightness=2.0)
    darker = _edit(img, brightness=0.5)
    assert _channel_mean(brighter) > _channel_mean(img)
    assert _channel_mean(darker) < _channel_mean(img)

    low = _edit(img, contrast=0.5)
    high = _edit(img, contrast=2.0)

    def spread(image: Image.Image) -> int:
        values = [pixel[0] for pixel in image.getdata()]
        return max(values) - min(values)

    assert spread(high) > spread(low)


def test_resolve_params_clamps_and_lowercases_filter() -> None:
    _, _, params = _resolve_params("", {"brightness": 10, "contrast": 0.01, "filter": "GrayScale"})
    assert params["brightness"] == 3.0
    assert params["contrast"] == 0.1
    assert params["filter"] == "grayscale"
    assert params["finish"] == "default"


def test_resolve_params_preset_then_override() -> None:
    name, label, params = _resolve_params("document", {"contrast": 1.2})
    assert name == "document"
    assert label == "Document"
    assert params["filter"] == "grayscale"
    assert params["equalize"] is True
    assert params["finish"] == "document"
    assert params["contrast"] == 1.2


def test_resolve_params_rejects_unknown_filter_and_preset() -> None:
    with pytest.raises(HTTPException) as unknown_filter:
        _resolve_params("", {"filter": "sepia"})
    assert unknown_filter.value.status_code == 400
    with pytest.raises(HTTPException) as unknown_preset:
        _resolve_params("not-a-preset", {})
    assert unknown_preset.value.status_code == 400


def test_apply_edits_grayscale_equalizes_channels() -> None:
    out = _edit(solid_image((6, 6), (255, 0, 0)), filter_name="grayscale")
    red, green, blue = out.getpixel((0, 0))
    assert out.mode == "RGB"
    assert red == green == blue
    assert 0 < red < 255


def test_apply_edits_blur_spreads_a_single_pixel() -> None:
    img = solid_image((15, 15), (0, 0, 0))
    img.putpixel((7, 7), (255, 255, 255))
    out = _edit(img, filter_name="blur")
    assert out.size == img.size
    assert out.getpixel((7, 7)) != (255, 255, 255)
    assert out.getpixel((6, 7)) != (0, 0, 0)


def test_apply_edits_sharpen_and_edge_keep_size() -> None:
    img = solid_image((20, 20), (40, 40, 40))
    for x in range(10, 20):
        for y in range(20):
            img.putpixel((x, y), (180, 180, 180))

    sharpened = _edit(img, filter_name="sharpen")
    edges = _edit(img, filter_name="edge")
    assert sharpened.size == img.size and sharpened.mode == "RGB"
    assert list(sharpened.getdata()) != list(img.getdata())
    assert edges.size == img.size and edges.mode == "RGB"
    assert any(pixel != (0, 0, 0) for pixel in edges.getdata())


def test_apply_edits_unknown_filter_matches_none() -> None:
    img = solid_image((8, 8), (30, 60, 90))
    assert list(_edit(img, filter_name="sepia").getdata()) == list(_edit(img).getdata())
    assert list(_edit(img, filter_name="").getdata()) == list(_edit(img).getdata())


def test_apply_edits_rotate_flip_saturation_and_invert() -> None:
    wide = solid_image((20, 10), (20, 40, 60))
    assert _edit(wide, rotate=90).size == (10, 20)

    marked = solid_image((4, 2), (0, 0, 0))
    marked.putpixel((0, 0), (255, 0, 0))
    flipped = _edit(marked, flip="horizontal")
    assert flipped.getpixel((3, 0)) == (255, 0, 0)
    assert flipped.getpixel((0, 0)) == (0, 0, 0)

    red, green, blue = _edit(solid_image((4, 4), (200, 40, 40)), saturation=0).getpixel((0, 0))
    assert red == green == blue

    inverted = _edit(solid_image((2, 2), (10, 20, 30)), invert=True)
    assert inverted.getpixel((0, 0)) == (245, 235, 225)


def test_apply_edits_posterize_colorize_and_extra_filters() -> None:
    mixed = solid_image((6, 6), (12, 80, 200))
    mixed.putpixel((0, 0), (240, 10, 10))
    poster = _edit(mixed, posterize=2)
    assert poster.size == mixed.size
    assert list(poster.getdata()) != list(mixed.getdata())

    tinted = _edit(solid_image((6, 6), (128, 128, 128)), colorize_black="#000000", colorize_white="#ff0000")
    red, green, blue = tinted.getpixel((0, 0))
    assert red > green and red > blue

    for name in ("contour", "emboss", "detail", "smooth", "edge_enhance"):
        out = _edit(mixed, filter_name=name)
        assert out.mode == "RGB"
        assert out.size == mixed.size


def test_cpu_generate_preserves_size_and_changes_low_contrast_image() -> None:
    img = _low_contrast()
    out = _cpu_generate(img)
    assert out.mode == "RGB"
    assert out.size == img.size
    assert list(out.getdata()) != list(img.getdata())


def test_cpu_generate_finish_modes_stay_on_cpu_pillow() -> None:
    img = _low_contrast()
    assert list(_cpu_generate(img, "none").getdata()) == list(img.getdata())
    assert list(_cpu_generate(img, "edits").getdata()) == list(img.getdata())
    for finish in ("default", "soft", "document"):
        out = _cpu_generate(img, finish)
        assert out.size == img.size
        assert list(out.getdata()) != list(img.getdata())


def test_cpu_generate_is_deterministic() -> None:
    img = solid_image((12, 10), (25, 25, 25))
    img.putpixel((3, 3), (250, 10, 10))
    first = list(_cpu_generate(img).getdata())
    second = list(_cpu_generate(img).getdata())
    assert first == second
