"""Original pixel art for the electronics episode.

Jazz Jackrabbit 2 reads chunky, outlined, palette-like sprites. These frames are
drawn here from scratch (no Epic tiles or enemy sheets). Index 0 is empty.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

W = H = 48

# Shared sprite palette. 0 is transparent.
PALETTE = {
    0: (0, 0, 0, 0),
    1: (18, 12, 22, 255),       # outline
    2: (255, 236, 214, 255),    # eye
    3: (42, 24, 28, 255),         # pupil
    4: (232, 206, 150, 255),    # resistor body
    5: (196, 154, 96, 255),     # resistor shade
    6: (122, 72, 36, 255),        # brown band
    7: (28, 28, 32, 255),         # black band
    8: (196, 48, 42, 255),       # red band
    9: (232, 184, 64, 255),      # gold
    10: (214, 220, 228, 255),     # lead / metal
    11: (120, 128, 140, 255),     # metal shade
    12: (72, 78, 92, 255),        # dark metal
    13: (86, 196, 255, 255),      # spark cyan
    14: (255, 244, 120, 255),     # spark yellow
    15: (255, 255, 255, 255),     # hot white
    16: (48, 56, 64, 255),        # plastic body
    17: (88, 98, 110, 255),       # plastic light
    18: (184, 96, 42, 255),       # copper
    19: (232, 154, 72, 255),      # copper light
    20: (92, 48, 28, 255),        # copper dark
    21: (64, 168, 86, 255),       # pcb green
    22: (36, 110, 64, 255),       # pcb dark
    23: (210, 214, 220, 255),     # can
    24: (140, 150, 164, 255),     # can shade
    25: (48, 96, 196, 255),       # stripe blue
    26: (255, 92, 64, 255),       # pop red
    27: (255, 160, 48, 255),      # pop orange
    28: (96, 64, 48, 255),        # boot
    29: (168, 176, 186, 255),     # tab
    30: (40, 44, 52, 255),        # hole
}

DARK = (16, 18, 28, 255)


def blank():
    return [[0] * W for _ in range(H)]


def put(img, x, y, c):
    if c and 0 <= x < W and 0 <= y < H:
        img[y][x] = c


def rect(img, x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put(img, xx, yy, c)


def frame_copy(img):
    return [row[:] for row in img]


def eyes(img, x, y, look=0):
    """Two chunky eyes. look: -1 left, 0 center, 1 right."""
    for i, ox in enumerate((0, 7)):
        rect(img, x + ox, y, 5, 5, 1)
        rect(img, x + ox + 1, y + 1, 3, 3, 2)
        px = x + ox + 2 + look
        put(img, px, y + 2, 3)
        put(img, px, y + 3, 3)


def feet(img, y, phase):
    """Two boots. phase 0..3 shifts them for a walk cycle."""
    shifts = [(0, 0), (2, -1), (0, 0), (-2, 1)]
    a, b = shifts[phase % 4]
    rect(img, 10 + a, y, 8, 4, 1)
    rect(img, 11 + a, y, 6, 3, 28)
    rect(img, 28 + b, y, 8, 4, 1)
    rect(img, 29 + b, y, 6, 3, 28)


def blob_outline(img, color_inside=None):
    """Turn the outer edge of filled pixels into the outline color."""
    src = frame_copy(img)
    for y in range(H):
        for x in range(W):
            if src[y][x]:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < W and 0 <= yy < H and src[yy][xx]:
                        img[y][x] = 1
                        break


def to_rgba(img, background=None):
    out = Image.new("RGBA", (W, H), background or (0, 0, 0, 0))
    px = out.load()
    for y in range(H):
        for x in range(W):
            px[x, y] = PALETTE[img[y][x]]
    return out


def sheet(frames, background=None):
    n = len(frames)
    canvas = Image.new("RGBA", (W * n, H), background or (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        canvas.paste(to_rgba(fr), (i * W, 0))
    return canvas


def upscale(image, scale=4, background=DARK):
    w, h = image.size
    base = Image.new("RGBA", (w, h), background)
    base.alpha_composite(image)
    return base.resize((w * scale, h * scale), Image.Resampling.NEAREST)


def save_preview(frames, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    upscale(sheet(frames)).save(path)


def save_game_sheet(frames, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet(frames).save(path)


# --- enemies ---------------------------------------------------------------

def resistor_frames():
    """Walking resistor: beige body, 1k colour bands, wire legs."""
    frames = []
    for phase in range(4):
        img = blank()
        bob = 1 if phase % 2 else 0
        y0 = 14 + bob
        # leads into the feet
        rect(img, 16, y0 + 12, 3, 10, 10)
        rect(img, 29, y0 + 12, 3, 10, 10)
        # body
        rect(img, 8, y0, 32, 14, 4)
        rect(img, 8, y0 + 10, 32, 4, 5)
        # end caps
        rect(img, 8, y0, 4, 14, 10)
        rect(img, 36, y0, 4, 14, 11)
        # colour bands: brown, black, red, gold (1 kΩ, 5%)
        rect(img, 14, y0, 3, 14, 6)
        rect(img, 19, y0, 3, 14, 7)
        rect(img, 24, y0, 3, 14, 8)
        rect(img, 31, y0, 2, 14, 9)
        eyes(img, 15, y0 + 3, look=(phase % 3) - 1)
        feet(img, 40 + bob, phase)
        blob_outline(img)
        frames.append(img)
    return frames


def resistor_debris():
    """A snapped colour-band and a curled lead, used when the walker is hit."""
    band = blank()
    rect(band, 16, 18, 16, 10, 4)
    rect(band, 18, 18, 3, 10, 6)
    rect(band, 22, 18, 3, 10, 7)
    rect(band, 26, 18, 3, 10, 8)
    blob_outline(band)
    lead = blank()
    for i, x in enumerate(range(12, 34, 3)):
        rect(lead, x, 20 + (i % 2), 4, 3, 10)
    blob_outline(lead)
    return [band, lead]
