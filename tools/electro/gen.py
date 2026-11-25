#!/usr/bin/env python3
"""Original Elektronika episode: JJ2-format levels plus sprite add-on files.

Nothing here is copied from Epic tiles or sprites. Original tilesets were only
a reminder of how Jazz Jackrabbit 2 shades a shape: dark outline, three tones,
a highlight on the upper-left.
"""

from __future__ import annotations

import math
import shutil
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("/opt/cursor/artifacts")
PACK = OUT / "elektronika-pack"

# Indexed tile palette. 0 is empty.
PAL = [
    (0, 0, 0),
    (20, 6, 14),       # 1 outline
    (14, 4, 18),       # 2 backdrop
    (28, 10, 36),      # 3 backdrop trace
    (18, 48, 28),      # 4 pcb dark
    (36, 92, 44),      # 5 pcb
    (86, 156, 62),     # 6 pcb light
    (120, 64, 24),     # 7 copper dark
    (186, 104, 40),    # 8 copper
    (240, 176, 78),    # 9 copper light
    (96, 58, 24),      # 10 brass dark
    (176, 116, 44),    # 11 brass
    (236, 196, 96),    # 12 brass light
    (46, 16, 48),      # 13 purple dark
    (104, 36, 112),    # 14 purple
    (168, 110, 210),   # 15 purple light
    (28, 16, 24),      # 16 iron dark
    (118, 124, 136),   # 17 iron
    (214, 220, 228),   # 18 iron light
    (150, 28, 32),     # 19 red
    (236, 210, 150),   # 20 beige
    (255, 244, 214),   # 21 shine
    (255, 248, 230),   # 22 eye
    (24, 8, 16),       # 23 pupil
    (70, 210, 255),    # 24 spark
    (255, 244, 120),   # 25 spark hot
    (40, 70, 170),     # 26 blue
    (64, 200, 84),     # 27 led
    (210, 160, 70),    # 28 solder
    (70, 36, 28),      # 29 boot
]
# pad to 256
while len(PAL) < 256:
    PAL.append((0, 0, 0))

W = H = 32


def blank():
    return [[0] * W for _ in range(H)]


def put(im, x, y, c):
    if 0 <= x < W and 0 <= y < H and c:
        im[y][x] = c


def rect(im, x, y, w, h, c):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put(im, xx, yy, c)


def shade(im, ramp):
    """Three-tone the filled pixels of `ramp` (dark, mid, light) plus outline."""
    dark, mid, light = ramp
    src = [row[:] for row in im]
    for y in range(H):
        for x in range(W):
            if src[y][x] != mid:
                continue
            up = y > 0 and src[y - 1][x] == mid
            left = x > 0 and src[y][x - 1] == mid
            down = y + 1 < H and src[y + 1][x] == mid
            right = x + 1 < W and src[y][x + 1] == mid
            if not up or not left:
                im[y][x] = light
            elif not down or not right:
                im[y][x] = dark
    # outline around anything non-zero that was part of this shape or already drawn
    src = [row[:] for row in im]
    for y in range(H):
        for x in range(W):
            if src[y][x]:
                continue
            if any(0 <= y + dy < H and 0 <= x + dx < W and src[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy):
                im[y][x] = 1


def fill_ellipse(im, cx, cy, rx, ry, c):
    for y in range(cy - ry - 1, cy + ry + 2):
        for x in range(cx - rx - 1, cx + rx + 2):
            if rx and ry and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                put(im, x, y, c)


def mask_bits(im, rows=None):
    bits = bytearray(128)
    for y in range(H):
        if rows is not None and y not in rows:
            continue
        for x in range(W):
            if im[y][x] == 0:
                continue
            i = y * W + x
            bits[i // 8] |= 1 << (i % 8)
    return bytes(bits)


def alpha_bits(im):
    return mask_bits(im, rows=range(H))


def idx_image(im):
    return bytes(im[y][x] for y in range(H) for x in range(W))


# --- tiles -----------------------------------------------------------------

def t_flat(c):
    im = blank()
    rect(im, 0, 0, 32, 32, c)
    return im


def t_pcb(traces=True):
    im = t_flat(4)
    for y in range(0, 32, 8):
        rect(im, 0, y, 32, 1, 5)
    if traces:
        rect(im, 0, 14, 32, 3, 8)
        rect(im, 0, 15, 32, 1, 9)
        rect(im, 14, 0, 3, 32, 8)
        rect(im, 15, 0, 1, 32, 9)
        fill_ellipse(im, 8, 8, 2, 2, 28)
        fill_ellipse(im, 24, 24, 2, 2, 28)
    return im


def t_trace_h():
    im = t_flat(2)
    rect(im, 0, 14, 32, 4, 3)
    rect(im, 0, 15, 32, 2, 8)
    rect(im, 0, 15, 32, 1, 9)
    return im


def t_trace_v():
    im = t_flat(2)
    rect(im, 14, 0, 4, 32, 3)
    rect(im, 15, 0, 2, 32, 8)
    rect(im, 15, 0, 1, 32, 9)
    return im


def t_brass(kind="full"):
    im = blank()
    if kind == "full":
        rect(im, 0, 0, 32, 32, 11)
        for x in range(4, 30, 7):
            rect(im, x, 3, 3, 26, 10)
        shade(im, (10, 11, 12))
        return im
    if kind == "top":
        rect(im, 0, 0, 32, 10, 11)
        shade(im, (10, 11, 12))
        return im
    if kind == "slopeR":
        for x in range(32):
            y0 = 31 - x
            for y in range(y0, 32):
                put(im, x, y, 11)
        shade(im, (10, 11, 12))
        return im
    if kind == "slopeL":
        for x in range(32):
            y0 = x
            for y in range(y0, 32):
                put(im, x, y, 11)
        shade(im, (10, 11, 12))
        return im
    return im


def t_core_block():
    im = blank()
    rect(im, 1, 1, 30, 30, 14)
    for y in range(5, 27, 5):
        rect(im, 3, y, 26, 2, 13)
    rect(im, 6, 6, 8, 20, 8)
    rect(im, 18, 6, 8, 20, 8)
    rect(im, 8, 8, 4, 16, 9)
    rect(im, 20, 8, 4, 16, 9)
    shade(im, (13, 14, 15))
    return im


def t_motor_block():
    im = blank()
    rect(im, 1, 1, 30, 30, 17)
    rect(im, 4, 6, 24, 3, 16)
    rect(im, 4, 14, 24, 3, 16)
    rect(im, 4, 22, 24, 3, 16)
    fill_ellipse(im, 16, 16, 6, 6, 16)
    fill_ellipse(im, 16, 16, 2, 2, 12)
    shade(im, (16, 17, 18))
    return im


def t_gear(angle):
    im = blank()
    cx = cy = 16
    for y in range(32):
        for x in range(32):
            dx, dy = x - cx + 0.5, y - cy + 0.5
            r = math.hypot(dx, dy)
            a = math.atan2(dy, dx) + angle
            tooth = math.cos(a * 8) > -0.05
            if r < 5:
                im[y][x] = 16
            elif r < 9:
                im[y][x] = 17
            elif r < 14 and tooth:
                im[y][x] = 11
    fill_ellipse(im, 16, 16, 3, 3, 1)
    put(im, 14, 15, 22)
    put(im, 18, 15, 22)
    put(im, 14, 16, 23)
    put(im, 18, 16, 23)
    shade(im, (10, 11, 12))
    return im


def t_led(on, color):
    im = t_pcb(False)
    fill_ellipse(im, 16, 16, 5, 5, color if on else 16)
    if on:
        put(im, 14, 14, 21)
    return im


def t_coil_frame(spark):
    im = blank()
    rect(im, 14, 2, 4, 28, 16)
    for y in range(4, 28, 4):
        rect(im, 6, y, 20, 2, 8)
        rect(im, 7, y, 18, 1, 9)
    if spark:
        put(im, 4, 8, 25)
        put(im, 3, 12, 24)
        put(im, 5, 16, 24)
        put(im, 27, 10, 25)
        put(im, 28, 18, 24)
    shade(im, (7, 8, 9))
    return im


def t_resistor_deco():
    im = blank()
    rect(im, 2, 14, 5, 3, 17)
    rect(im, 25, 14, 5, 3, 17)
    rect(im, 6, 10, 20, 12, 20)
    rect(im, 9, 10, 2, 12, 29)
    rect(im, 13, 10, 2, 12, 1)
    rect(im, 17, 10, 2, 12, 19)
    rect(im, 21, 10, 2, 12, 12)
    shade(im, (29, 20, 21))
    return im


def t_cap_deco():
    im = blank()
    rect(im, 10, 4, 12, 20, 17)
    rect(im, 10, 4, 3, 20, 26)
    rect(im, 13, 24, 2, 6, 17)
    rect(im, 17, 24, 2, 6, 17)
    shade(im, (16, 17, 18))
    return im


def t_mos_deco():
    im = blank()
    rect(im, 9, 4, 14, 16, 17)
    fill_ellipse(im, 16, 8, 2, 2, 1)
    rect(im, 11, 20, 2, 8, 17)
    rect(im, 15, 20, 2, 8, 17)
    rect(im, 19, 20, 2, 8, 17)
    put(im, 24, 14, 24)
    put(im, 26, 12, 25)
    shade(im, (16, 17, 18))
    return im


def t_hazard():
    im = blank()
    rect(im, 0, 0, 32, 32, 16)
    for i in range(-32, 32, 8):
        for y in range(32):
            for k in range(4):
                put(im, i + y + k, y, 12)
    shade(im, (16, 12, 21))
    return im


def t_exit():
    im = blank()
    rect(im, 4, 2, 24, 28, 11)
    rect(im, 8, 6, 16, 18, 2)
    rect(im, 12, 10, 8, 5, 27)
    rect(im, 14, 18, 4, 4, 12)
    shade(im, (10, 11, 12))
    return im


def build_tiles():
    tiles = []

    def add(im, solid):
        if solid == "full":
            rows = range(32)
        elif solid == "top":
            rows = range(0, 12)
        elif solid == "slope":
            rows = None  # use alpha of drawn pixels
        elif solid == "none":
            rows = []
        else:
            rows = solid
        m = alpha_bits(im) if solid == "slope" else (mask_bits(im, rows) if solid != "none" else bytes(128))
        tiles.append((im, m))

    add(blank(), "none")             # 0
    add(t_flat(2), "none")           # 1 backdrop
    add(t_pcb(True), "none")         # 2 pcb
    add(t_pcb(False), "none")        # 3 pcb plain
    add(t_trace_h(), "none")         # 4
    add(t_trace_v(), "none")         # 5
    add(t_brass("full"), "full")     # 6
    add(t_brass("top"), "top")       # 7
    add(t_brass("slopeR"), "slope")  # 8
    add(t_brass("slopeL"), "slope")  # 9
    add(t_core_block(), "full")      # 10
    add(t_motor_block(), "full")     # 11
    add(t_gear(0.0), "full")         # 12
    add(t_gear(0.4), "full")         # 13
    add(t_gear(0.8), "full")         # 14
    add(t_gear(1.2), "full")         # 15
    add(t_led(True, 27), "none")     # 16
    add(t_led(False, 16), "none")    # 17
    add(t_coil_frame(False), "none") # 18
    add(t_coil_frame(True), "none")  # 19
    add(t_resistor_deco(), "none")   # 20
    add(t_cap_deco(), "none")        # 21
    add(t_mos_deco(), "none")        # 22
    add(t_hazard(), "full")          # 23
    add(t_exit(), "none")            # 24
    return tiles


# animated tile ids (version 0x202, 4 anims): 1020..1023
GEAR, LED, COIL, TRACE = 1020, 1021, 1022, 1023


# --- RGBA sprites ----------------------------------------------------------

def new_rgba(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _shift(c, amt):
    return tuple(max(0, min(255, c[i] + amt)) for i in range(3)) + (c[3],)


def blit_shade(im, color_dark=None, color_mid=None, color_light=None, outline=(22, 8, 16, 255)):
    """Lighten the upper-left rim and darken the lower-right rim of whatever was drawn."""
    w, h = im.size
    src = im.load()
    out = new_rgba(w, h)
    px = out.load()
    for y in range(h):
        for x in range(w):
            c = src[x, y]
            if c[3] < 128:
                continue
            up = y > 0 and src[x, y - 1][3] >= 128
            left = x > 0 and src[x - 1, y][3] >= 128
            down = y + 1 < h and src[x, y + 1][3] >= 128
            right = x + 1 < w and src[x + 1, y][3] >= 128
            if not up or not left:
                px[x, y] = _shift(c, 48)
            elif not down or not right:
                px[x, y] = _shift(c, -42)
            else:
                px[x, y] = c
    # outline
    base = out.copy()
    bp = base.load()
    op = out.load()
    for y in range(h):
        for x in range(w):
            if bp[x, y][3] >= 128:
                continue
            if any(0 <= x + dx < w and 0 <= y + dy < h and bp[x + dx, y + dy][3] >= 128
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy):
                op[x, y] = outline
    return out


def paste(dst, src, x, y):
    dst.alpha_composite(src, (x, y))


def blob(w, h, color):
    im = new_rgba(w, h)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), fill=color)
    return im


def ellipse(w, h, color):
    im = new_rgba(w, h)
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, w - 1, h - 1), fill=color)
    return im


def eyes(im, x, y, look=0):
    d = ImageDraw.Draw(im)
    for i in range(2):
        ox = x + i * 8
        d.rectangle((ox, y, ox + 5, y + 5), fill=(255, 248, 230, 255))
        d.point((ox + 2 + look, y + 2), fill=(24, 8, 16, 255))
        d.point((ox + 2 + look, y + 3), fill=(24, 8, 16, 255))


def resistor_frames():
    frames = []
    body_c = (210, 168, 110, 255)
    for i in range(6):
        im = new_rgba(48, 48)
        bob = 1 if i % 2 else 0
        # body
        paste(im, blob(28, 14, body_c), 10, 14 + bob)
        shaded = blit_shade(im, (120, 78, 40, 255), (210, 168, 110, 255), (245, 224, 180, 255))
        # bands and leads on top of shade
        d = ImageDraw.Draw(shaded)
        d.rectangle((6, 18 + bob, 12, 22 + bob), fill=(180, 186, 194, 255))
        d.rectangle((36, 18 + bob, 42, 22 + bob), fill=(140, 146, 156, 255))
        d.rectangle((14, 14 + bob, 16, 27 + bob), fill=(122, 72, 36, 255))
        d.rectangle((18, 14 + bob, 20, 27 + bob), fill=(24, 16, 22, 255))
        d.rectangle((22, 14 + bob, 24, 27 + bob), fill=(176, 40, 36, 255))
        d.rectangle((30, 14 + bob, 32, 27 + bob), fill=(220, 176, 64, 255))
        eyes(shaded, 16, 17 + bob, look=(i % 3) - 1)
        # feet
        shift = [0, 2, 0, -2, 1, -1][i]
        d.rectangle((12 + shift, 34, 20 + shift, 38), fill=(70, 40, 28, 255))
        d.rectangle((26 - shift, 34, 34 - shift, 38), fill=(50, 28, 20, 255))
        d.rectangle((12 + shift, 34, 20 + shift, 35), fill=(22, 8, 16, 255))
        frames.append(shaded)
    # hurt
    hurt = frames[0].copy()
    hp = hurt.load()
    for y in range(48):
        for x in range(48):
            if hp[x, y][3] > 200 and (x + y) % 3 == 0:
                hp[x, y] = (255, 244, 210, 255)
    frames.append(hurt)
    return frames


def debris_frame():
    im = new_rgba(24, 16)
    d = ImageDraw.Draw(im)
    d.rectangle((2, 4, 18, 12), fill=(210, 168, 110, 255))
    d.rectangle((6, 4, 8, 12), fill=(176, 40, 36, 255))
    d.rectangle((11, 4, 13, 12), fill=(24, 16, 22, 255))
    d.rectangle((1, 4, 19, 5), fill=(22, 8, 16, 255))
    return im


def mosfet_frames():
    frames = []
    for i in range(6):
        im = new_rgba(48, 48)
        paste(im, blob(20, 18, (150, 156, 170, 255)), 12, 8)
        paste(im, ellipse(8, 6, (40, 44, 52, 255)), 18, 6)
        shaded = blit_shade(im, (70, 74, 86, 255), (150, 156, 170, 255), (220, 224, 232, 255))
        d = ImageDraw.Draw(shaded)
        for n, x in enumerate((16, 22, 28)):
            d.rectangle((x, 26, x + 2, 40), fill=(186, 192, 200, 255))
            d.rectangle((x, 26, x + 2, 27), fill=(22, 8, 16, 255))
        # spark
        if i % 2 == 0:
            d.point((34, 18), fill=(255, 244, 140, 255))
            d.point((36, 16), fill=(80, 220, 255, 255))
            d.point((33, 21), fill=(80, 220, 255, 255))
        else:
            d.point((35, 15), fill=(255, 255, 220, 255))
            d.point((37, 19), fill=(80, 220, 255, 255))
            d.point((32, 20), fill=(255, 244, 140, 255))
        eyes(shaded, 16, 14, look=1 if i > 2 else 0)
        frames.append(shaded)
    return frames


def gear_frames():
    frames = []
    for i in range(4):
        im = new_rgba(48, 48)
        ang = i * (math.pi / 8)
        px = im.load()
        for y in range(48):
            for x in range(48):
                dx, dy = x - 23.5, y - 22.5
                r = math.hypot(dx, dy)
                a = math.atan2(dy, dx) + ang
                if r < 7:
                    px[x, y] = (90, 70, 110, 255)
                elif r < 12:
                    px[x, y] = (140, 110, 160, 255)
                elif r < 20 and math.cos(a * 8) > -0.05:
                    px[x, y] = (190, 140, 50, 255)
        shaded = blit_shade(im, (90, 60, 24, 255), (176, 120, 48, 255), (240, 200, 100, 255))
        eyes(shaded, 16, 18, look=(i % 3) - 1)
        frames.append(shaded)
    # attack: brighter teeth
    atk = frames[0].copy()
    ap = atk.load()
    for y in range(48):
        for x in range(48):
            if ap[x, y][3] > 200 and ap[x, y][0] > 160:
                ap[x, y] = (255, 220, 120, 255)
    frames.append(atk)
    return frames


def coil_frames(big=False):
    frames = []
    w = 56 if big else 48
    for i in range(6):
        im = new_rgba(w, 48)
        d = ImageDraw.Draw(im)
        cx = w // 2
        d.rectangle((cx - 3, 6, cx + 3, 40), fill=(70, 50, 90, 255))
        for y in range(8, 40, 4):
            d.rectangle((cx - 14, y, cx + 14, y + 2), fill=(176, 96, 36, 255))
            d.rectangle((cx - 14, y, cx + 14, y), fill=(236, 170, 80, 255))
        # arcs
        phase = i % 3
        d.line((cx - 16, 12 + phase, cx - 20, 20, cx - 14, 28), fill=(120, 230, 255, 255))
        d.line((cx + 16, 14, cx + 22, 22 + phase, cx + 15, 32), fill=(255, 244, 140, 255))
        if big and i % 2 == 0:
            d.line((8, 18, 4, 24, 10, 30), fill=(255, 255, 220, 255))
        eyes(im, cx - 8, 18, look=1 if i > 2 else -1)
        frames.append(im)
    return frames


def capacitor_frames():
    frames = []
    for i in range(6):
        im = new_rgba(48, 48)
        bob = i % 2
        paste(im, blob(16, 22, (200, 206, 214, 255)), 16, 8 + bob)
        shaded = blit_shade(im, (90, 96, 108, 255), (190, 196, 206, 255), (240, 242, 246, 255))
        d = ImageDraw.Draw(shaded)
        d.rectangle((16, 8 + bob, 20, 30 + bob), fill=(48, 78, 180, 255))
        d.rectangle((20, 32, 22, 40), fill=(150, 90, 40, 255))
        d.rectangle((26, 32, 28, 40), fill=(120, 74, 36, 255))
        # minus marks
        for y in range(12, 26, 4):
            d.point((24, y + bob), fill=(40, 44, 52, 255))
        if i >= 4:
            d.rectangle((14, 4, 34, 10), fill=(255, 236, 120, 255))
            d.point((12, 6), fill=(255, 80, 60, 255))
            d.point((36, 5), fill=(120, 230, 255, 255))
        frames.append(shaded)
    return frames


def boss_frames():
    """Huge transformer. Several states share sheets."""
    def base(sparks, blades):
        im = new_rgba(96, 96)
        d = ImageDraw.Draw(im)
        # iron body
        d.rectangle((18, 28, 78, 88), fill=(120, 90, 150, 255))
        d.rectangle((28, 16, 68, 36), fill=(90, 64, 120, 255))
        # copper windings
        for y in range(34, 80, 6):
            d.rectangle((24, y, 44, y + 3), fill=(176, 96, 36, 255))
            d.rectangle((52, y, 72, y + 3), fill=(200, 120, 48, 255))
            d.line((24, y, 72, y), fill=(240, 180, 80, 255))
        # core
        d.rectangle((44, 30, 52, 84), fill=(60, 40, 80, 255))
        if blades:
            d.polygon([(48, 18), (10, 22), (48, 26)], fill=(200, 206, 214, 255))
            d.polygon([(48, 18), (86, 22), (48, 26)], fill=(160, 166, 176, 255))
        if sparks:
            d.line((8, 40, 4, 52, 12, 64), fill=(120, 230, 255, 255))
            d.line((88, 44, 92, 56, 84, 70), fill=(255, 244, 140, 255))
            d.point((6, 48), fill=(255, 255, 220, 255))
        eyes(im, 36, 40, look=-1 if sparks else 0)
        # feet
        d.rectangle((26, 86, 42, 94), fill=(70, 40, 28, 255))
        d.rectangle((54, 86, 70, 94), fill=(50, 28, 20, 255))
        return im

    idle = [base(False, False), base(True, False)]
    run = [base(False, False), base(True, False), base(False, False), base(True, False)]
    # bob the run frames by cropping shift
    attack = [base(True, False) for _ in range(3)]
    copter = [base(True, True), base(False, True)]
    shrap = []
    for color in ((240, 180, 80, 255), (120, 230, 255, 255), (200, 206, 214, 255)):
        s = new_rgba(16, 16)
        ImageDraw.Draw(s).ellipse((2, 2, 13, 13), fill=color)
        shrap.append(s)
    return {"idle": idle, "run": run, "attack": attack, "copter": copter, "shrap": shrap}


def sheet(frames, scale=1):
    w, h = frames[0].size
    out = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        out.alpha_composite(fr, (i * w, 0))
    if scale != 1:
        out = out.resize((out.width * scale, out.height * scale), Image.Resampling.NEAREST)
    return out


def anim_res(frame_w, frame_h, count, hotspot):
    return (
        '{\n'
        '  "Flags": 0,\n'
        f'  "FrameCount": {count},\n'
        f'  "FrameSize": [{frame_w}, {frame_h}],\n'
        f'  "FrameConfiguration": [{count}, 1],\n'
        f'  "Hotspot": [{hotspot[0]}, {hotspot[1]}],\n'
        f'  "Coldspot": [{hotspot[0]}, {hotspot[1]}]\n'
        '}\n'
    )


def meta(anims):
    lines = ['{', '  "Version": { "Target": "Jazz² Resurrection" },', '  "Animations": {']
    body = []
    for name, path, states, rate in anims:
        st = ", ".join(str(s) for s in states)
        rate_l = f'\n      "FrameRate": {rate},' if rate else ""
        body.append(
            f'    "{name}": {{\n      "Path": "{path}",{rate_l}\n      "States": [{st}]\n    }}'
        )
    lines.append(",\n".join(body))
    lines.append("  }\n}\n")
    return "\n".join(lines)


# --- j2 writers ------------------------------------------------------------

def fixed(text, n):
    raw = text.encode("latin1", "replace")[: n - 1]
    return raw + b"\x00" * (n - len(raw))


def pack_block(raw: bytes) -> bytes:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return b"\x78\xda" + co.compress(raw) + co.flush()


def write_j2t(path: Path, tiles):
    max_tiles = 1024
    count = len(tiles)
    images = b"".join(idx_image(im) for im, _ in tiles)
    alphas = b"".join(alpha_bits(im) for im, _ in tiles)
    masks = b"".join(m for _, m in tiles)
    pal = bytearray()
    for i, (r, g, b) in enumerate(PAL):
        a_file = 255 if i == 0 else 0
        pal += struct.pack("<I", r | (g << 8) | (b << 16) | (a_file << 24))
    info = bytearray(pal)
    info += struct.pack("<i", count)
    info += bytes(max_tiles * 2)
    for i in range(count):
        info += struct.pack("<I", i * 1024)
    info += bytes(4 * (max_tiles - count))
    info += bytes(4 * max_tiles)
    for i in range(count):
        info += struct.pack("<I", i * 128)
    info += bytes(4 * (max_tiles - count))
    info += bytes(4 * max_tiles)
    for i in range(count):
        info += struct.pack("<I", i * 128)
    info += bytes(4 * (max_tiles - count))
    info += bytes(4 * max_tiles)
    blocks = [pack_block(bytes(info)), pack_block(images), pack_block(alphas), pack_block(masks)]
    raws = [bytes(info), images, alphas, masks]
    notice = b"Elektronika tiles. Original art, not Epic MegaGames."[:180].ljust(180, b" ")
    header = bytearray(82)
    struct.pack_into("<I", header, 0, 0x454C4954)
    struct.pack_into("<I", header, 4, 0xAFBEADDE)
    header[8:40] = fixed("Elektro", 32)
    struct.pack_into("<H", header, 40, 0x200)
    off = 50
    for packed, raw in zip(blocks, raws):
        struct.pack_into("<ii", header, off, len(packed), len(raw))
        off += 8
    body_len = 180 + 82 + sum(len(b) for b in blocks)
    struct.pack_into("<i", header, 42, body_len)
    path.write_bytes(notice + bytes(header) + b"".join(blocks))


def enc_fixed(value):
    return struct.pack("<i", int(round(value * 65536)))


def write_j2l(path, display, tileset, music, nxt, width, height, layers_tiles, events, anims):
    """layers_tiles: list of (index, tiles, speed, depth) for non-sprite, plus sprite is index 3."""
    max_tiles = 1024
    anim_count = len(anims)

    def layer_meta():
        used = [False] * 8
        widths = [0] * 8
        heights = [0] * 8
        depths = [0] * 8
        speeds = [0.0] * 8
        used[3] = True
        widths[3] = width
        heights[3] = height
        speeds[3] = 1.0
        for idx, _tiles, speed, depth in layers_tiles:
            used[idx] = True
            widths[idx] = width
            heights[idx] = height
            speeds[idx] = speed
            depths[idx] = depth
        buf = bytearray()
        buf += b"".join(struct.pack("<I", 0) for _ in range(8))
        buf += bytes(8)
        buf += bytes(1 if u else 0 for u in used)
        buf += b"".join(struct.pack("<i", w) for w in widths)
        buf += b"".join(struct.pack("<i", w) for w in widths)
        buf += b"".join(struct.pack("<i", h) for h in heights)
        buf += b"".join(struct.pack("<i", d) for d in depths)
        buf += bytes(8)
        buf += b"".join(enc_fixed(0) for _ in range(8))
        buf += b"".join(enc_fixed(0) for _ in range(8))
        buf += b"".join(enc_fixed(speeds[i]) for i in range(8))
        buf += b"".join(enc_fixed(speeds[i]) for i in range(8))
        buf += b"".join(enc_fixed(0) for _ in range(16))
        buf += bytes(8)
        buf += bytes(24)
        return buf, used

    info = bytearray(9)
    info += bytes([64, 64])
    info += struct.pack("<H", anim_count)
    info += bytes([0, 0])
    info += struct.pack("<i", 0)
    info += fixed(display, 32)
    info += fixed(tileset, 32)
    info += fixed("", 32)
    info += fixed(nxt, 32)
    info += fixed("", 32)
    info += fixed(music, 32)
    info += b"\x00" * (16 * 512)
    meta, used = layer_meta()
    info += meta
    info += struct.pack("<H", max_tiles - anim_count)
    info += b"\x00" * (max_tiles * 4)
    info += bytes(max_tiles)
    info += bytes(max_tiles)
    info += bytes(max_tiles)
    for delay, speed, frames in anims:
        info += struct.pack("<HHH", delay, 0, 0)
        info += bytes([0, speed, len(frames)])
        padded = list(frames) + [0] * (64 - len(frames))
        info += b"".join(struct.pack("<H", f) for f in padded)

    ev = b"".join(struct.pack("<I", w) for w in events)

    # dictionary shared by every used layer, layout in index order
    words = []
    index = {}

    def layout_for(tiles):
        raw = bytearray()
        for y in range(height):
            for x in range(0, width, 4):
                word = tuple(tiles[y * width + x + j] for j in range(4))
                if word not in index:
                    index[word] = len(words)
                    words.append(word)
                raw += struct.pack("<H", index[word])
        return bytes(raw)

    layouts = {}
    # sprite first among its index; we emit in layer index order
    sprite = None
    extras = {idx: tiles for idx, tiles, _s, _d in layers_tiles}
    for idx in range(8):
        if idx == 3:
            layouts[3] = layout_for(layers_tiles and extras.get(3) or None) if False else None
    # The caller passes sprite tiles separately as the first return via parameter `events` sibling.
    # See write_level wrapper.


def write_level_file(path, display, tileset, music, nxt, width, height, sprite, extras, events, anims):
    """extras: list of (layerIndex, tiles, speed, depth). sprite is layer 3."""
    max_tiles = 1024
    anim_count = len(anims)
    used = {3}
    speeds = {3: 1.0}
    depths = {3: 0}
    tilemaps = {3: sprite}
    for idx, tiles, speed, depth in extras:
        used.add(idx)
        speeds[idx] = speed
        depths[idx] = depth
        tilemaps[idx] = tiles

    info = bytearray(9)
    info += bytes([64, 64])
    info += struct.pack("<H", anim_count)
    info += bytes([0, 0])
    info += struct.pack("<i", 0)
    info += fixed(display, 32)
    info += fixed(tileset, 32)
    info += fixed("", 32)
    info += fixed(nxt, 32)
    info += fixed("", 32)
    info += fixed(music, 32)
    info += b"\x00" * (16 * 512)
    flags = b"".join(struct.pack("<I", 0) for _ in range(8))
    types = bytes(8)
    used_b = bytes(1 if i in used else 0 for i in range(8))
    def arr(fn):
        return b"".join(fn(i) for i in range(8))
    widths = arr(lambda i: struct.pack("<i", width if i in used else 0))
    heights = arr(lambda i: struct.pack("<i", height if i in used else 0))
    depthb = arr(lambda i: struct.pack("<i", depths.get(i, 0)))
    detail = bytes(8)
    z = b"".join(enc_fixed(0) for _ in range(8))
    sx = arr(lambda i: enc_fixed(speeds.get(i, 0)))
    info += flags + types + used_b + widths + widths + heights + depthb + detail + z + z + sx + sx
    info += b"".join(enc_fixed(0) for _ in range(16))
    info += bytes(8) + bytes(24)
    info += struct.pack("<H", max_tiles - anim_count)
    info += b"\x00" * (max_tiles * 4) + bytes(max_tiles) + bytes(max_tiles) + bytes(max_tiles)
    for _delay, speed, frames in anims:
        info += struct.pack("<HHH", 0, 0, 0)
        info += bytes([0, speed, len(frames)])
        padded = list(frames) + [0] * (64 - len(frames))
        info += b"".join(struct.pack("<H", f) for f in padded)

    ev = b"".join(struct.pack("<I", w) for w in events)
    words = []
    index = {}

    def layout_for(tiles):
        raw = bytearray()
        for y in range(height):
            row = y * width
            for x in range(0, width, 4):
                word = tuple(tiles[row + x + j] for j in range(4))
                if word not in index:
                    index[word] = len(words)
                    words.append(word)
                raw += struct.pack("<H", index[word])
        return bytes(raw)

    layouts = []
    for i in range(8):
        if i in used:
            layouts.append(layout_for(tilemaps[i]))
    dict_raw = b"".join(struct.pack("<HHHH", *w) for w in words)
    layout_raw = b"".join(layouts)
    blocks_raw = [bytes(info), ev, dict_raw, layout_raw]
    blocks = [pack_block(r) for r in blocks_raw]
    notice = b"Elektronika level. Original, not Epic MegaGames."[:180].ljust(180, b" ")
    header = bytearray(82)
    struct.pack_into("<I", header, 0, 0x4C56454C)
    header[8:40] = fixed(display, 32)
    struct.pack_into("<H", header, 40, 0x202)
    off = 50
    for packed, raw in zip(blocks, blocks_raw):
        struct.pack_into("<ii", header, off, len(packed), len(raw))
        off += 8
    body_len = 180 + 82 + sum(len(b) for b in blocks)
    struct.pack_into("<i", header, 42, body_len)
    path.write_bytes(notice + bytes(header) + b"".join(blocks))


def write_j2e(path: Path):
    buf = bytearray(208)
    struct.pack_into("<i", buf, 0, 208)
    struct.pack_into("<i", buf, 4, 9)
    struct.pack_into("<I", buf, 8, 1)
    buf[16:80] = fixed("Elektronika", 64)
    buf[144:176] = fixed("Plyta", 32)
    path.write_bytes(bytes(buf))


def ev(kind, params=0):
    return (kind & 0xFF) | ((params & 0xFFFFF) << 12)


# tile ids
EMPTY, BACK, PCB, PCB2, TRACE_H, TRACE_V, BRASS, PLAT, SLOPER, SLOPEL, CORE, MOTOR = range(12)
G0, G1, G2, G3 = 12, 13, 14, 15
LED_ON, LED_OFF, COIL0, COIL1 = 16, 17, 18, 19
RES_D, CAP_D, MOS_D, HAZ, EXIT = 20, 21, 22, 23, 24


class L:
    def __init__(self, w, h):
        self.w, self.h = w, h
        n = w * h
        self.s = [0] * n
        self.back = [BACK] * n
        self.mid = [0] * n
        self.events = [0] * n

    def t(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.s[y * self.w + x] = v

    def m(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.mid[y * self.w + x] = v

    def b(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.back[y * self.w + x] = v

    def e(self, x, y, word):
        if 0 <= x < self.w and 0 <= y < self.h and self.events[y * self.w + x] == 0:
            self.events[y * self.w + x] = word

    def solid_from(self, x0, x1, y, tile=BRASS):
        for x in range(x0, x1):
            for yy in range(y, self.h):
                self.t(x, yy, tile)

    def platform(self, x0, x1, y, tile=PLAT):
        for x in range(x0, x1):
            self.t(x, y, tile)

    def deco_band(self):
        for x in range(0, self.w, 6):
            self.b(x, 4, PCB if (x // 6) % 2 == 0 else PCB2)
            self.m(x, 8, TRACE_H if (x // 12) % 2 == 0 else TRACE_V)
            self.m(x + 2, 12, LED)


def build_level1():
    w, h = 220, 24
    # width must be multiple of 4
    L1 = L(w, h)
    L1.deco_band()
    floor = 20
    # walls and ceiling
    for y in range(h):
        L1.t(0, y, BRASS)
        L1.t(1, y, BRASS)
        L1.t(w - 2, y, BRASS)
        L1.t(w - 1, y, BRASS)
    for x in range(w):
        L1.t(x, 0, BRASS)
    L1.solid_from(0, w, floor, BRASS)

    # start hall
    L1.e(4, floor - 1, ev(0x1D))
    for i, kind in enumerate((0x2D, 0x2C, 0x3F, 0x40, 0x41, 0x42, 0x2D, 0x3F)):
        L1.e(6 + i, floor - 1, ev(kind))
    L1.t(8, floor - 4, RES_D)
    L1.t(14, floor - 5, MOS_D)
    L1.e(18, floor - 1, ev(0x6B))  # sparks / mosfet
    L1.e(24, floor - 1, ev(0x73))  # skeleton / resistor

    # gap + spring
    for x in range(30, 36):
        for y in range(floor, h):
            L1.t(x, y, 0)
    L1.solid_from(36, 44, floor - 3, BRASS)
    L1.e(37, floor - 4, ev(0x55))
    L1.e(40, floor - 4, ev(0x3F))

    # gear factory
    for x in range(46, 96):
        L1.t(x, floor - 1, GEAR)
        L1.e(x, floor - 1, ev(0x0A, 3))
    for x in (52, 64, 78, 90):
        L1.e(x, floor - 2, ev(0x7E))  # fencer / trybik
    for x in range(50, 94, 4):
        L1.e(x, floor - 3, ev(0x2D))
    # secret above the belt
    L1.platform(60, 78, floor - 8, PLAT)
    for x in range(60, 78):
        L1.e(x, floor - 8, ev(0x01))
    L1.e(68, floor - 9, ev(0x43))  # super gem
    L1.e(72, floor - 9, ev(0x60))  # fly carrot
    L1.t(62, floor - 10, CAP_D)

    # checkpoint grove
    L1.e(100, floor - 1, ev(0x53))
    L1.e(102, floor - 1, ev(0x48))
    L1.e(104, floor - 1, ev(0x3D))  # fast fire
    # resistor forest: stepping stones
    y = floor
    for x in range(108, 150, 6):
        y = floor - (2 if (x // 6) % 2 == 0 else 0)
        L1.solid_from(x, x + 4, y, BRASS)
        L1.t(x + 1, y - 2, RES_D)
        if (x // 6) % 2 == 0:
            L1.e(x + 1, y - 1, ev(0x73))
        else:
            L1.e(x + 2, y - 1, ev(0x6B))
        L1.e(x, y - 1, ev(0x40))
    # fill the pits between stones so it stays fair: they are real gaps of 2 tiles
    # (solid_from only covers 4 of each 6)

    # transformer stairs
    base = 156
    for step, yy in enumerate(range(floor, floor - 10, -2)):
        L1.solid_from(base + step * 4, base + step * 4 + 5, yy, CORE)
        if step % 2 == 0:
            L1.e(base + step * 4 + 1, yy - 1, ev(0x55))
        L1.t(base + step * 4 + 2, yy - 3, COIL)
    L1.e(base + 6, floor - 8, ev(0x69))   # bee
    L1.e(base + 14, floor - 12, ev(0x7B))  # dragonfly
    L1.e(base + 20, floor - 6, ev(0x58))  # invincible, tucked on a step

    # capacitor bank
    L1.solid_from(196, 218, floor, BRASS)
    for x in (198, 204, 210):
        L1.e(x, floor - 1, ev(0x7D))
        L1.t(x, floor - 3, CAP_D)
        L1.e(x + 1, floor - 1, ev(0x41))
    L1.e(214, floor - 1, ev(0x53))
    L1.t(216, floor - 4, EXIT)
    L1.e(216, floor - 1, ev(0x51))
    L1.e(217, floor - 2, ev(0x11))
    return L1


def build_level2():
    w, h = 168, 32
    L2 = L(w, h)
    L2.deco_band()
    floor = 28
    for y in range(h):
        L2.t(0, y, MOTOR)
        L2.t(1, y, MOTOR)
    for x in range(w):
        L2.t(x, 0, BRASS)
    L2.solid_from(0, 70, floor, MOTOR)
    L2.e(4, floor - 1, ev(0x1D))
    L2.e(6, floor - 1, ev(0x2D))
    L2.e(8, floor - 1, ev(0x3F))
    L2.e(12, floor - 1, ev(0x6A))  # rapier / charging coil
    # gearbox corridor with slopes
    L2.solid_from(20, 28, floor - 2, BRASS)
    for x in range(28, 36):
        L2.t(x, floor - 2 - (x - 28), SLOPER)
        for y in range(floor - 1 - (x - 28), h):
            if L2.s[y * w + x] == 0:
                L2.t(x, y, BRASS)
    L2.solid_from(36, 60, floor - 8, BRASS)
    for x in range(40, 58, 6):
        L2.e(x, floor - 9, ev(0x7E))
        L2.t(x, floor - 11, 15)  # a gear frame, not the anim, as decoration
    L2.e(48, floor - 9, ev(0x50))  # 1-up
    # drop
    L2.solid_from(64, 100, floor, BRASS)
    for x in (70, 78, 86, 94):
        L2.e(x, floor - 1, ev(0x7D))
        L2.t(x, floor - 3, CAP_D)
        L2.e(x + 2, floor - 2, ev(LED) if False else ev(0x3F))
    L2.e(66, floor - 1, ev(0x53))
    L2.e(68, floor - 1, ev(0x48))
    # boss arena
    L2.solid_from(104, 160, floor, CORE)
    for x in range(108, 150):
        L2.t(x, floor - 8, 0)  # headroom already empty
    L2.e(112, floor - 1, ev(0x1C))  # activate boss, music boss1
    L2.e(132, floor - 1, ev(0xCA))  # robot boss
    L2.t(124, floor - 6, COIL)
    L2.t(140, floor - 6, COIL)
    L2.e(150, floor - 1, ev(0x43))
    L2.t(156, floor - 4, EXIT)
    L2.e(156, floor - 1, ev(0x51))
    L2.e(158, floor - 2, ev(0x11))
    # a raised rescue platform if the boss knocks you around
    L2.platform(118, 128, floor - 6, PLAT)
    for x in range(118, 128):
        L2.e(x, floor - 6, ev(0x01))
    return L2


def save_addon(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)

    def put_anim(rel_png, frames):
        # rel like Elektro/rezystor_walk.png
        png = folder / "Animations" / rel_png
        png.parent.mkdir(parents=True, exist_ok=True)
        sheet(frames).save(png)
        w, h = frames[0].size
        (png.parent / (png.name + ".res")).write_text(
            anim_res(w, h, len(frames), (w // 2, h - 2)), encoding="utf-8"
        )

    def put_meta(rel, text):
        p = folder / "Metadata" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    rez = resistor_frames()
    put_anim("Elektro/rezystor_walk.png", rez[:6])
    put_anim("Elektro/rezystor_hurt.png", [rez[6]])
    bit = debris_frame()
    put_anim("Elektro/rezystor_bit.png", [bit, bit])
    put_meta("Rezystor/WalkX.res", meta([
        ("Walk", "Elektro/rezystor_walk.png", [1], 8),
        ("Hurt", "Elektro/rezystor_hurt.png", [4], 0),
        ("Bit", "Elektro/rezystor_bit.png", [2, 3], 0),
    ]))

    mos = mosfet_frames()
    put_anim("Elektro/mosfet.png", mos)
    put_meta("Mosfet/Spark.res", meta([
        ("Idle", "Elektro/mosfet.png", [0], 10),
    ]))

    gear = gear_frames()
    put_anim("Elektro/trybik_idle.png", gear[:4])
    put_anim("Elektro/trybik_atk.png", gear[4:])
    put_meta("Trybik/GearX.res", meta([
        ("Idle", "Elektro/trybik_idle.png", [0], 8),
        ("Attack", "Elektro/trybik_atk.png", [1325400065], 10),
    ]))

    coil = coil_frames(False)
    put_anim("Elektro/cewka.png", coil)
    put_anim("Elektro/cewka_turn.png", [coil[0], coil[3]])
    put_meta("Cewka/Dragonfly.res", meta([
        ("Idle", "Elektro/cewka.png", [0], 12),
    ]))
    put_meta("Cewka/Bee.res", meta([
        ("Idle", "Elektro/cewka.png", [0], 12),
        ("Turn", "Elektro/cewka_turn.png", [1073741840], 14),
    ]))
    big = coil_frames(True)
    put_anim("Elektro/cewka_charge.png", big)
    put_meta("Cewka/Charge.res", meta([
        ("Idle", "Elektro/cewka_charge.png", [0], 8),
        ("Attack", "Elektro/cewka_charge.png", [1073741824], 8),
        ("AttackStart", "Elektro/cewka_charge.png", [1073741825], 10),
        ("AttackEnd", "Elektro/cewka_charge.png", [1073741826], 10),
        ("Swing", "Elektro/cewka_charge.png", [1073741827], 8),
    ]))

    cap = capacitor_frames()
    put_anim("Elektro/kondens_walk.png", cap[:4])
    put_anim("Elektro/kondens_pop.png", cap[4:])
    put_meta("Kondens/Attack.res", meta([
        ("Walk", "Elektro/kondens_walk.png", [1], 8),
        ("Attack", "Elektro/kondens_pop.png", [1325400065], 8),
    ]))

    boss = boss_frames()
    put_anim("Elektro/trafo_idle.png", boss["idle"])
    put_anim("Elektro/trafo_run.png", boss["run"])
    put_anim("Elektro/trafo_atk.png", boss["attack"])
    put_anim("Elektro/trafo_copter.png", boss["copter"])
    put_anim("Elektro/trafo_shrap.png", boss["shrap"])
    put_meta("Trafo/Boss.res", meta([
        ("Idle", "Elektro/trafo_idle.png", [0], 4),
        ("Run", "Elektro/trafo_run.png", [2], 8),
        ("AttackStart", "Elektro/trafo_atk.png", [1073741824], 8),
        ("Attack", "Elektro/trafo_atk.png", [1073741825], 12),
        ("AttackEnd", "Elektro/trafo_atk.png", [1073741826], 8),
        ("Copter", "Elektro/trafo_copter.png", [1073741828], 10),
        ("CopterEnd", "Elektro/trafo_copter.png", [1073741829], 8),
        ("Spike", "Elektro/trafo_shrap.png", [1073741827], 6),
        ("S1", "Elektro/trafo_shrap.png", [100], 0),
        ("S2", "Elektro/trafo_shrap.png", [101, 102], 0),
        ("S3", "Elektro/trafo_shrap.png", [103, 104, 105], 0),
        ("S4", "Elektro/trafo_shrap.png", [106, 107, 108], 0),
    ]))
    return {
        "rezystor": rez[:6],
        "mosfet": mos,
        "trybik": gear[:4],
        "cewka": coil,
        "kondensator": cap,
        "trafo": boss["idle"],
    }


def tileset_preview(tiles, path):
    cols = 8
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new("RGBA", (cols * 32, rows * 32), (20, 8, 18, 255))
    px = im.load()
    for i, (tile, _) in enumerate(tiles):
        ox, oy = (i % cols) * 32, (i // cols) * 32
        for y in range(32):
            for x in range(32):
                c = tile[y][x]
                r, g, b = PAL[c]
                px[ox + x, oy + y] = (r, g, b, 0 if c == 0 else 255)
    im = im.resize((im.width * 2, im.height * 2), Image.Resampling.NEAREST)
    im.save(path)


def contact_sheet(enemies, path):
    # each row: name + frames at 2x
    rows = []
    font = ImageFont.load_default()
    for name, frames in enemies.items():
        pic = sheet(frames, scale=2)
        canvas = Image.new("RGBA", (max(pic.width, 240), pic.height + 16), (16, 10, 18, 255))
        d = ImageDraw.Draw(canvas)
        d.text((4, 0), name, fill=(255, 220, 140, 255), font=font)
        canvas.alpha_composite(pic, (0, 14))
        rows.append(canvas)
    w = max(r.width for r in rows)
    h = sum(r.height for r in rows) + 8
    out = Image.new("RGBA", (w, h), (12, 6, 14, 255))
    y = 4
    for r in rows:
        out.alpha_composite(r, (4, y))
        y += r.height
    out.save(path)


def flatten_addon(src: Path, dest: Path):
    """Write jj2addon__ files into dest (the zip root)."""
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        name = "jj2addon__" + rel.replace("/", "__")
        shutil.copy(p, dest / name)


def czyta():
    return """Elektronika — epizod do Jazz Jackrabbit 2
==========================================

Jak wgrać na iPhonie (Safari):
1. Rozpakuj tego zipa.
2. Skopiuj do głównego katalogu gry (tam, gdzie jest Anims.j2a) pliki:
   Electro.j2e, Electro.j2t, Plyta.j2l, Plyta2.j2l
   oraz WSZYSTKIE pliki jj2addon__… (to własne duszki).
   Nie trzeba kopiować katalogu podglad/.
3. Otwórz stronę gry. Stuknij „Wgraj pliki ponownie”.
4. W Plikach zaznacz wszystko w tym katalogu (także jj2addon__) i potwierdź.
5. „Graj” → pomiń intro → Nowa gra → Elektronika.
   Najpierw „Plyta drukowana”, potem drugi poziom.
6. Sterowanie jest w silniku. Nakładka HTML jest wyłączona,
   dopóki w adresie nie ma ?overlay=1.

Duszki Rezystora, MOSFET-a, Trybika, Cewki, Kondensatora i wielkiego
transformatora włączają się tylko na tych dwóch planszach. W innych
epizodach wrogowie zostają tacy jak w oryginale.

Na planszy: start, monety, klejnoty, las oporników, taśmociąg zębatek,
sekret nad taśmą, rdzeń transformatora, bateria kondensatorów, a na
drugim poziomie skrzynia biegów i boss-transformator.
Muzyka: tubelec.j2b, potem labrat.j2b, przy bossie boss1.j2b.
"""


def main():
    if PACK.exists():
        shutil.rmtree(PACK)
    PACK.mkdir(parents=True)
    tiles = build_tiles()
    write_j2t(PACK / "Electro.j2t", tiles)
    anims = [
        (0, 8, [12, 13, 14, 15]),   # gear -> id 1020
        (0, 6, [16, 17]),           # led
        (0, 10, [18, 19, 18, 19]),  # coil
        (0, 8, [4, 5]),             # trace
    ]
    L1 = build_level1()
    assert L1.w % 4 == 0
    write_level_file(
        PACK / "Plyta.j2l", "Plyta drukowana", "Electro", "tubelec", "unknown/plyta2",
        L1.w, L1.h, L1.s,
        [(7, L1.back, 0.25, 320), (6, L1.mid, 0.55, 140)],
        L1.events, anims,
    )
    L2 = build_level2()
    assert L2.w % 4 == 0
    write_level_file(
        PACK / "Plyta2.j2l", "Silnik i transformator", "Electro", "labrat", "end",
        L2.w, L2.h, L2.s,
        [(7, L2.back, 0.22, 320), (6, L2.mid, 0.5, 150)],
        L2.events, anims,
    )
    write_j2e(PACK / "Electro.j2e")
    addon = PACK / "_addon"
    enemies = save_addon(addon)
    flatten_addon(addon, PACK)
    shutil.rmtree(addon)
    (PACK / "CZYTAJ.txt").write_text(czyta(), encoding="utf-8")
    preview = PACK / "podglad"
    preview.mkdir()
    tileset_preview(tiles, preview / "tileset.png")
    contact_sheet(enemies, preview / "enemies.png")
    tileset_preview(tiles, OUT / "tileset.png")
    contact_sheet(enemies, OUT / "enemies-contact.png")
    (OUT / "CZYTAJ.txt").write_text(czyta(), encoding="utf-8")
    zip_path = OUT / "elektronika-jazz2.zip"
    if zip_path.exists():
        zip_path.unlink()
    # zip without the nested pack name: contents at the root. Skip nothing.
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", PACK)
    print("levels", L1.w, L1.h, L2.w, L2.h)
    print("addon files", sum(1 for p in PACK.glob("jj2addon__*")))
    print("zip", zip_path, zip_path.stat().st_size)


if __name__ == "__main__":
    main()
