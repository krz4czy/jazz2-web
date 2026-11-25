"""Original enemy sprites for the Elektronika episode.

Drawn from scratch. Jazz Jackrabbit 2's look — a dark outline, a light from
the upper left, a shadow on the lower right — is the only thing borrowed.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw

OUTLINE = (16, 6, 18, 255)


def new_rgba(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def volume(im, amt=62):
    """Shade a filled shape as if the light sits up and to the left."""
    w, h = im.size
    src = im.load()
    alpha = [[src[x, y][3] >= 128 for x in range(w)] for y in range(h)]
    out = im.copy()
    px = out.load()
    for y in range(h):
        for x in range(w):
            if not alpha[y][x]:
                continue

            def a(yy, xx):
                return 1 if 0 <= yy < h and 0 <= xx < w and alpha[yy][xx] else 0

            nx = (a(y - 1, x + 1) + 2 * a(y, x + 1) + a(y + 1, x + 1)
                  - a(y - 1, x - 1) - 2 * a(y, x - 1) - a(y + 1, x - 1))
            ny = (a(y + 1, x - 1) + 2 * a(y + 1, x) + a(y + 1, x + 1)
                  - a(y - 1, x - 1) - 2 * a(y - 1, x) - a(y - 1, x + 1))
            mag = math.hypot(nx, ny)
            if mag < 2.2:
                ndotl = 0.35 - (y / max(1, h - 1)) * 0.7
            else:
                ndotl = (nx * -0.62 + ny * -0.88) / mag
            add = int(max(-1, min(1, ndotl)) * amt)
            c = src[x, y]
            px[x, y] = tuple(max(0, min(255, c[i] + add)) for i in range(3)) + (255,)
    return out


def outline(im, color=OUTLINE):
    w, h = im.size
    src = im.load()
    out = im.copy()
    px = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3] >= 128:
                continue
            hit = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if not dx and not dy:
                        continue
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h and src[xx, yy][3] >= 128:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                px[x, y] = color
    return out


def finish(im):
    return outline(volume(im))


def eyes(d, x, y, look=0, brow=True):
    for i in range(2):
        ox = x + i * 8
        d.rectangle((ox, y, ox + 5, y + 5), fill=(255, 246, 220, 255))
        d.point((ox + 1, y + 1), fill=(255, 255, 255, 255))
        px = ox + 2 + look
        d.rectangle((px, y + 2, px + 1, y + 4), fill=(28, 10, 18, 255))
        if brow:
            d.line((ox - 1, y - 2, ox + 5, y), fill=(28, 10, 18, 255))


def bolt(d, x0, y0, x1, y1, phase, color=(120, 230, 255, 255), hot=(255, 255, 210, 255)):
    pts = [(x0, y0)]
    steps = 5
    for s in range(1, steps):
        t = s / steps
        jag = (1 if (s + phase) % 2 == 0 else -1) * (3 + (s % 3))
        pts.append((int(x0 + (x1 - x0) * t + jag), int(y0 + (y1 - y0) * t)))
    pts.append((x1, y1))
    d.line(pts, fill=color)
    d.line(pts[1:-1], fill=hot)


def boot(d, x, y, w=8, h=7):
    d.rectangle((x, y, x + w, y + h), fill=(78, 42, 28, 255))
    d.rectangle((x, y, x + w, y + 1), fill=(28, 12, 16, 255))
    d.rectangle((x, y + h - 2, x + w, y + h), fill=(40, 20, 16, 255))
    d.point((x + 1, y + 2), fill=(140, 90, 56, 255))


def resistor_frames():
    frames = []
    body = (214, 170, 108, 255)
    for i in range(6):
        im = new_rgba(56, 48)
        d = ImageDraw.Draw(im)
        bob = [0, 0, 1, 1, 0, 0][i]
        phase = i % 4
        ldx = [0, 4, 0, -4][phase]
        rdx = [0, -3, 0, 4][phase]
        # leads
        d.rectangle((4, 20 + bob, 14, 24 + bob), fill=(186, 192, 202, 255))
        d.rectangle((42, 20 + bob, 52, 24 + bob), fill=(150, 158, 170, 255))
        # ceramic body
        d.ellipse((10, 12 + bob, 26, 32 + bob), fill=body)
        d.ellipse((30, 12 + bob, 46, 32 + bob), fill=body)
        d.rectangle((16, 12 + bob, 40, 32 + bob), fill=body)
        shaded = volume(im)
        d = ImageDraw.Draw(shaded)
        # color bands, 1 kΩ: brown, black, red, gold
        for x, col in ((16, (122, 72, 36, 255)), (22, (24, 16, 22, 255)),
                       (28, (186, 42, 40, 255)), (36, (220, 176, 64, 255))):
            d.rectangle((x, 12 + bob, x + 2, 32 + bob), fill=col)
            d.point((x, 14 + bob), fill=(255, 236, 200, 255))
        d.point((18, 16 + bob), fill=(255, 244, 214, 255))
        d.point((19, 16 + bob), fill=(255, 244, 214, 255))
        eyes(d, 20, 16 + bob, look=(i % 3) - 1)
        boot(d, 14 + ldx, 36, 9, 7)
        boot(d, 32 + rdx, 36, 9, 7)
        frames.append(outline(shaded))
    hurt = frames[0].copy()
    hp = hurt.load()
    w, h = hurt.size
    for y in range(h):
        for x in range(w):
            if hp[x, y][3] > 200 and (x + y) % 2 == 0:
                hp[x, y] = (255, 244, 220, 255)
    frames.append(hurt)
    return frames


def debris_frame():
    im = new_rgba(28, 18)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 3, 24, 14), radius=3, fill=(214, 170, 108, 255))
    d.rectangle((7, 3, 9, 14), fill=(186, 42, 40, 255))
    d.rectangle((13, 3, 15, 14), fill=(24, 16, 22, 255))
    d.rectangle((18, 3, 20, 14), fill=(220, 176, 64, 255))
    return outline(im)


def mosfet_frames():
    frames = []
    for i in range(6):
        im = new_rgba(52, 56)
        d = ImageDraw.Draw(im)
        bob = 1 if i % 2 else 0
        # metal tab
        d.rounded_rectangle((16, 4 + bob, 36, 16 + bob), radius=2, fill=(176, 184, 196, 255))
        d.ellipse((23, 6 + bob, 29, 12 + bob), fill=(40, 28, 36, 255))
        # epoxy body
        d.rectangle((12, 14 + bob, 40, 36 + bob), fill=(168, 176, 188, 255))
        d.rectangle((14, 16 + bob, 38, 18 + bob), fill=(210, 216, 224, 255))
        shaded = volume(im)
        d = ImageDraw.Draw(shaded)
        d.ellipse((24, 7 + bob, 28, 11 + bob), fill=(20, 12, 18, 255))
        d.point((25, 8 + bob), fill=(230, 236, 240, 255))
        eyes(d, 18, 22 + bob, look=1 if i > 2 else 0, brow=False)
        # three legs
        for n, x in enumerate((18, 25, 32)):
            lean = [0, 1, -1][n] if i % 2 else 0
            d.rectangle((x, 36 + bob, x + 2, 48), fill=(196, 202, 210, 255))
            d.rectangle((x + lean, 46, x + 3 + lean, 50), fill=(140, 148, 160, 255))
        # spark leaping off the drain leg
        if i % 2 == 0:
            bolt(d, 36, 20 + bob, 48, 10 + (i % 4), i, (90, 220, 255, 255))
            bolt(d, 38, 28 + bob, 50, 34, i + 1, (255, 236, 120, 255), (255, 255, 230, 255))
        else:
            bolt(d, 38, 16 + bob, 50, 22, i, (255, 244, 160, 255), (255, 255, 240, 255))
            bolt(d, 36, 30 + bob, 47, 40, i + 2, (80, 210, 255, 255))
        frames.append(outline(shaded))
    return frames


def gear_frames():
    frames = []

    def one(angle, bite=0, bright=False):
        im = new_rgba(52, 52)
        px = im.load()
        cx = cy = 25.5
        for y in range(52):
            for x in range(52):
                dx, dy = x - cx, y - cy
                r = math.hypot(dx, dy)
                a = math.atan2(dy, dx) + angle
                tooth = math.cos(a * 8) > -0.15
                if r < 8:
                    px[x, y] = (120, 86, 150, 255)
                elif r < 14:
                    px[x, y] = (168, 122, 64, 255)
                elif r < 22 and tooth:
                    px[x, y] = (196, 140, 52, 255) if not bright else (240, 200, 90, 255)
        # bite a notch out of the attack frames so the lunge reads
        if bite:
            d = ImageDraw.Draw(im)
            d.rectangle((4, 22, 14, 30), fill=(0, 0, 0, 0))
        shaded = volume(im, amt=70)
        d = ImageDraw.Draw(shaded)
        d.ellipse((20, 20, 32, 32), fill=(86, 48, 110, 255))
        d.ellipse((22, 22, 30, 30), fill=(40, 22, 58, 255))
        eyes(d, 18, 22, look=1 if angle > 1 else -1, brow=False)
        d.point((23, 23), fill=(255, 220, 140, 255))
        return outline(shaded)

    for i in range(4):
        frames.append(one(i * (math.pi / 8)))
    for i in range(3):
        frames.append(one(i * 0.5 + 0.2, bite=1, bright=True))
    return frames


def coil_frames(big=False):
    frames = []
    w = 60 if big else 52
    h = 52 if big else 48
    for i in range(6):
        im = new_rgba(w, h)
        d = ImageDraw.Draw(im)
        cx = w // 2
        bob = i % 2
        # ferrite core
        d.rectangle((cx - 4, 8, cx + 4, h - 10), fill=(78, 56, 96, 255))
        # copper turns
        for y in range(10, h - 12, 4):
            d.rounded_rectangle((cx - 16, y, cx + 16, y + 3), radius=1, fill=(176, 96, 40, 255))
        shaded = volume(im, amt=54)
        d = ImageDraw.Draw(shaded)
        for y in range(10, h - 12, 4):
            d.line((cx - 14, y, cx + 12, y), fill=(236, 176, 86, 255))
            d.line((cx - 14, y + 2, cx + 14, y + 2), fill=(110, 58, 24, 255))
        eyes(d, cx - 8, 18 + bob, look=1 if i > 2 else -1)
        # arcs
        bolt(d, cx - 16, 14, 6, 24 + (i % 3) * 4, i, (110, 230, 255, 255))
        bolt(d, cx + 16, 16, w - 6, 30 + bob * 4, i + 1, (255, 230, 120, 255), (255, 255, 220, 255))
        if big and i % 2 == 0:
            bolt(d, 8, 34, 4, 44, i, (255, 255, 230, 255), (120, 230, 255, 255))
            bolt(d, w - 8, 32, w - 4, 46, i + 2)
        if i >= 4:
            d.point((cx, 12), fill=(255, 255, 230, 255))
            d.point((cx - 1, 13), fill=(255, 244, 140, 255))
        frames.append(outline(shaded))
    return frames


def capacitor_frames():
    frames = []
    for i in range(6):
        im = new_rgba(44, 52)
        d = ImageDraw.Draw(im)
        bob = [0, 1, 0, 1, 0, 2][i]
        popped = i >= 4
        top = 6 + bob if not popped else 10
        # can
        d.rounded_rectangle((12, top, 32, 36 + bob), radius=3, fill=(198, 206, 214, 255))
        d.rectangle((12, top, 18, 36 + bob), fill=(58, 92, 190, 255))
        # crimped top
        if not popped:
            d.rectangle((14, top - 3, 30, top + 1), fill=(160, 168, 178, 255))
            d.point((22, top - 1), fill=(255, 255, 255, 255))
        shaded = volume(im, amt=48)
        d = ImageDraw.Draw(shaded)
        # minus marks on the sleeve
        for y in range(top + 6, 32 + bob, 4):
            d.line((20, y, 26, y), fill=(70, 78, 90, 255))
        d.line((18, top + 2, 30, top + 2), fill=(255, 255, 255, 255))
        eyes(d, 18, top + 8, look=(i % 3) - 1, brow=popped)
        # legs
        shift = [0, 2, 0, -2, 1, 0][i]
        d.rectangle((16 + shift, 36 + bob, 19 + shift, 46), fill=(150, 96, 48, 255))
        d.rectangle((26 - shift, 36 + bob, 29 - shift, 46), fill=(120, 74, 36, 255))
        if popped:
            d.polygon([(14, 8), (22, 2), (30, 9), (24, 12)], fill=(255, 236, 140, 255))
            d.point((10, 6), fill=(255, 80, 60, 255))
            d.point((34, 4), fill=(120, 230, 255, 255))
            d.point((36, 10), fill=(255, 244, 180, 255))
            d.ellipse((18, 0, 26, 6), fill=(255, 250, 230, 255))
        frames.append(outline(shaded))
    return frames


def boss_frames():
    """A walking substation. Big enough to read as the robot boss."""

    def body(sparks, blades, phase):
        im = new_rgba(96, 104)
        d = ImageDraw.Draw(im)
        # tank
        d.rounded_rectangle((16, 36, 80, 90), radius=4, fill=(118, 86, 156, 255))
        # lid
        d.rectangle((22, 28, 74, 42), fill=(86, 58, 120, 255))
        # bushings
        d.rectangle((30, 16, 40, 32), fill=(150, 90, 48, 255))
        d.rectangle((56, 16, 66, 32), fill=(176, 110, 52, 255))
        d.ellipse((31, 10, 39, 18), fill=(220, 200, 140, 255))
        d.ellipse((57, 10, 65, 18), fill=(220, 200, 140, 255))
        # core window
        d.rectangle((40, 44, 56, 82), fill=(48, 28, 70, 255))
        shaded = volume(im, amt=52)
        d = ImageDraw.Draw(shaded)
        # windings
        for y in range(46, 80, 5):
            d.rectangle((22, y, 40, y + 3), fill=(176, 96, 36, 255))
            d.rectangle((56, y, 74, y + 3), fill=(196, 120, 48, 255))
            d.line((22, y, 38, y), fill=(240, 186, 90, 255))
            d.line((56, y, 72, y), fill=(240, 186, 90, 255))
        d.rectangle((46, 44, 50, 82), fill=(70, 46, 100, 255))
        eyes(d, 36, 52, look=-1 if phase % 2 == 0 else 1)
        # feet, offset so the run cycle steps
        step = [0, 3, 0, -3][phase % 4]
        boot(d, 24 + step, 90, 14, 8)
        boot(d, 58 - step, 90, 14, 8)
        if blades:
            ang = phase * 0.8
            for k in range(3):
                a = ang + k * (math.pi * 2 / 3)
                x1 = 48 + int(math.cos(a) * 36)
                y1 = 18 + int(math.sin(a) * 8)
                d.line((48, 18, x1, y1), fill=(210, 216, 224, 255), width=2)
            d.ellipse((44, 14, 52, 22), fill=(40, 24, 56, 255))
        if sparks:
            bolt(d, 30, 14, 8, 28 + phase, phase, (120, 230, 255, 255))
            bolt(d, 66, 14, 90, 30 + phase, phase + 1, (255, 236, 130, 255), (255, 255, 220, 255))
            bolt(d, 18, 60, 6, 72, phase + 2)
        return outline(shaded)

    idle = [body(False, False, 0), body(True, False, 1)]
    run = [body(False, False, i) for i in range(4)]
    attack = [body(True, False, i) for i in range(3)]
    copter = [body(True, True, i) for i in range(4)]
    # nine distinct scraps, one per shrapnel state, packed in threes
    scraps = []
    colors = (
        (240, 180, 80, 255), (120, 230, 255, 255), (200, 206, 214, 255),
        (176, 96, 36, 255), (118, 86, 156, 255), (255, 244, 160, 255),
        (80, 48, 28, 255), (220, 200, 140, 255), (186, 42, 40, 255),
    )
    for i, color in enumerate(colors):
        s = new_rgba(16, 16)
        d = ImageDraw.Draw(s)
        if i % 3 == 0:
            d.ellipse((2, 2, 13, 13), fill=color)
        elif i % 3 == 1:
            d.polygon([(8, 1), (14, 14), (2, 14)], fill=color)
        else:
            d.rectangle((3, 3, 12, 12), fill=color)
        scraps.append(outline(s))
    return {
        "idle": idle,
        "run": run,
        "attack": attack,
        "copter": copter,
        "shrap": scraps,
    }
