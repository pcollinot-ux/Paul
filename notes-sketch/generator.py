#!/usr/bin/env python3
"""Arte-style hand-drawn music notes floating away. Generates RGBA frames."""
import math, random, subprocess, sys, os
import numpy as np
from PIL import Image, ImageDraw

W, H = 1920, 1080
SS = 2
FPS = 25
DUR = 10.0
N_FRAMES = int(DUR * FPS)
SS_W, SS_H = W * SS, H * SS
BG = (18, 18, 20)
FF = subprocess.check_output(
    ["python3", "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"]
).decode().strip()

TAU = 2 * math.pi


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def catmull_rom(pts, samples=14):
    if len(pts) < 3:
        return list(pts)
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def wobble(pts, seed, amp=2.4):
    rng = random.Random(seed)
    k1, k2 = rng.uniform(0.04, 0.09), rng.uniform(0.10, 0.18)
    f1, f2 = rng.uniform(0, TAU), rng.uniform(0, TAU)
    # cumulative arc length
    s = [0.0]
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        s.append(s[-1] + math.hypot(dx, dy))
    out = []
    for i, (x, y) in enumerate(pts):
        # normal
        if i == 0:
            tx, ty = pts[1][0] - x, pts[1][1] - y
        elif i == len(pts) - 1:
            tx, ty = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            tx, ty = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        d = s[i]
        off = amp * (0.65 * math.sin(k1 * d + f1) + 0.35 * math.sin(k2 * d + f2))
        off += rng.uniform(-0.5, 0.5)
        out.append((x + nx * off, y + ny * off))
    return out


def ellipse_pts(cx, cy, rx, ry, rot_deg, n=30):
    a = math.radians(rot_deg)
    pts = []
    for i in range(n + 1):
        t = TAU * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(a) - y * math.sin(a),
                    cy + x * math.sin(a) + y * math.cos(a)))
    return pts


def rot_pt(p, a):
    return (p[0] * math.cos(a) - p[1] * math.sin(a),
            p[0] * math.sin(a) + p[1] * math.cos(a))


def head_hatch(cx=0, cy=0, rx=24, ry=17, rot=-20):
    a = math.radians(rot)
    strokes = []
    for u in (-0.58, -0.2, 0.18, 0.55):
        yy = ry * math.sqrt(max(0.0, 1 - u * u)) * 0.82
        p1 = rot_pt((u * rx, -yy), a)
        p2 = rot_pt((u * rx * 0.92, yy), a)
        strokes.append(([(p1[0] + cx, p1[1] + cy), (p2[0] + cx, p2[1] + cy)], 3, True))
    return strokes


def g_quarter():
    head = (ellipse_pts(0, 0, 24, 17, -20), 4, False)
    stem = ([(21, -6), (23, -55), (25, -102)], 5, True)
    return dict(strokes=[head] + head_hatch() + [stem])


def g_eighth():
    base = g_quarter()
    flag = ([(25, -102), (52, -95), (68, -74), (60, -52), (68, -30)], 5, True)
    return dict(strokes=base["strokes"] + [flag])


def g_beamed(n_heads=2, beams=1):
    strokes = []
    step = 80
    top = -104
    for i in range(n_heads):
        hx = i * step
        hy = -i * 8
        strokes.append((ellipse_pts(hx, hy, 24, 17, -20), 4, False))
        strokes += head_hatch(cx=hx, cy=hy)
        sx = hx + 21
        strokes.append(([(sx, hy - 6), (sx + 2, hy - 55), (sx + 3, top - i * 6 + hy)], 5, True))
    for b in range(beams):
        y0 = top + b * 11
        strokes.append(([(24, y0), (24 + step * (n_heads - 1) + 3, y0 - 6 - (n_heads - 1) * 8 * 0)],
                        6, True))
    return dict(strokes=strokes)


def g_clef():
    body = [(-14, 98), (-4, 92), (6, 80), (10, 60), (12, 20), (12, -30),
            (10, -60), (14, -80), (26, -92), (40, -84), (42, -68), (32, -56),
            (16, -52), (0, -48), (-14, -40), (-20, -24), (-14, -8), (2, 0),
            (14, -6), (16, -20), (6, -28), (-6, -26), (-10, -16), (-4, -8)]
    tail = ([(-14, 98), (-22, 92), (-26, 82), (-20, 74)], 5, True)
    return dict(strokes=[(body, 5, True), tail])


def g_sparkle():
    return dict(strokes=[
        ([(0, -13), (0, 13)], 3, False),
        ([(-11, -7), (11, 7)], 3, False),
        ([(-11, 7), (11, -7)], 3, False),
    ])


def g_staff():
    strokes = []
    for i in range(5):
        y = i * 16
        strokes.append(([(0, y), (70, y - 1), (140, y + 1), (210, y)], 4, True))
    return dict(strokes=strokes)


GLYPHS = [
    (g_quarter, 3.0), (g_eighth, 3.5), (lambda: g_beamed(2, 1), 3.0),
    (lambda: g_beamed(2, 2), 2.0), (lambda: g_beamed(3, 1), 1.5),
    (g_sparkle, 1.2),
]


class Note:
    def __init__(self, rng):
        kind = rng.random()
        if kind < 0.10:
            self.glyph = g_clef()
            self.s = rng.uniform(1.3, 1.9)
            self.alpha = rng.uniform(0.45, 0.65)
        elif kind < 0.20:
            self.glyph = g_staff()
            self.s = rng.uniform(0.8, 1.2)
            self.alpha = rng.uniform(0.30, 0.42)
            self.speed = rng.uniform(20, 35)
        else:
            r = rng.random()
            acc = 0.0
            total = sum(w for _, w in GLYPHS)
            self.glyph = g_quarter()
            for fn, w in GLYPHS:
                acc += w / total
                if r <= acc:
                    self.glyph = fn()
                    break
            self.s = rng.uniform(0.8, 1.7)
            self.alpha = rng.uniform(0.75, 1.0)
        self.x0 = rng.uniform(180, W - 180)
        self.y0 = rng.uniform(500, 960)
        self.birth = rng.uniform(0, DUR - 3.4)
        if not hasattr(self, "speed"):
            self.speed = rng.uniform(40, 80)
        self.sway_amp = rng.uniform(10, 36)
        self.sway_f = rng.uniform(0.12, 0.38)
        self.phase = rng.uniform(0, TAU)
        self.rot0 = rng.uniform(-0.3, 0.3)
        self.rot_amp = rng.uniform(0.03, 0.12)
        self.rot_f = rng.uniform(0.15, 0.45)
        self.seed = rng.randrange(10 ** 6)

    def state(self, t):
        age = t - self.birth
        y = self.y0 - self.speed * max(0.0, age)
        x = self.x0 + self.sway_amp * math.sin(TAU * self.sway_f * t + self.phase)
        rot = self.rot0 + self.rot_amp * math.sin(TAU * self.rot_f * t + self.phase * 1.7)
        a = self.alpha * clamp(age / 0.35)
        if y < 320:
            a *= clamp((y - 90) / 230)
        return x, y, rot, a, age


def draw_glyph(d, glyph, x, y, rot, scale, alpha, reveal, boil, seed):
    strokes = glyph["strokes"]
    nt = len(strokes)
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    base_a = int(235 * alpha)
    if base_a <= 2:
        return
    for i, (pts, wd, smooth) in enumerate(strokes):
        frac = clamp(reveal * nt - i * 0.8)
        if frac <= 0.02:
            continue
        P = catmull_rom(pts) if smooth else list(pts)
        TP = []
        for px, py in P:
            px, py = px * scale, py * scale
            qx = px * ca - py * sa + x
            qy = px * sa + py * ca + y
            TP.append((qx * SS, qy * SS))
        for pas in range(2):
            sseed = hash((seed, i, pas, boil)) % (10 ** 6)
            WP = wobble(TP, sseed, amp=2.2)
            n = max(2, int(len(WP) * frac))
            seg = WP[:n]
            w = max(2, int(wd * scale * SS * 0.9))
            col = base_a if pas == 0 else int(base_a * 0.55)
            d.line(seg, fill=col, width=w, joint="curve")
            if frac > 0.05:
                r = w / 2
                for e in (seg[0], seg[-1]):
                    d.ellipse([e[0] - r, e[1] - r, e[0] + r, e[1] + r], fill=col)


def render_mask(fi, notes):
    mask = Image.new("L", (SS_W, SS_H), 0)
    d = ImageDraw.Draw(mask)
    t = fi / FPS
    boil = fi // 3
    for note in notes:
        x, y, rot, a, age = note.state(t)
        if a <= 0.02 or y < -80 or y > H + 200:
            continue
        reveal = clamp(age / 1.0)
        draw_glyph(d, note.glyph, x, y, math.degrees(rot), note.s, a, reveal, boil, note.seed)
    return mask.resize((W, H), Image.LANCZOS)


def mask_to_rgba(mask):
    arr = np.asarray(mask, dtype=np.float32) / 255.0 * 235.0
    rgba = np.empty((H, W, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 1] = 255
    rgba[..., 2] = 255
    rgba[..., 3] = arr.astype(np.uint8)
    return rgba


def mask_to_rgb_on_bg(mask, bg=BG):
    arr = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
    bgc = np.array(bg, dtype=np.float32)
    rgb = bgc * (1 - arr) + 255.0 * arr
    return rgb.astype(np.uint8)


def start_encoder(args):
    return subprocess.Popen([FF, "-y", "-hide_banner", "-loglevel", "error"] + args, stdin=subprocess.PIPE)


def main():
    rng = random.Random(42)
    notes = [Note(rng) for _ in range(20)]
    os.makedirs("/workspace/out", exist_ok=True)

    enc_alpha_rle = start_encoder([
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "qtrle", "-pix_fmt", "argb",
        "/workspace/out/notes_sketch_alpha_rle.mov",
    ])
    enc_alpha_prores = start_encoder([
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0",
        "/workspace/out/notes_sketch_alpha_prores4444.mov",
    ])
    enc_mp4 = start_encoder([
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "/workspace/out/notes_sketch_dark.mp4",
    ])

    for fi in range(N_FRAMES):
        mask = render_mask(fi, notes)
        rgba_bytes = mask_to_rgba(mask).tobytes()
        enc_alpha_rle.stdin.write(rgba_bytes)
        enc_alpha_prores.stdin.write(rgba_bytes)
        enc_mp4.stdin.write(mask_to_rgb_on_bg(mask).tobytes())
        if fi % 50 == 0:
            print(f"frame {fi}/{N_FRAMES}", flush=True)

    for enc in (enc_alpha_rle, enc_alpha_prores, enc_mp4):
        enc.stdin.close()
        enc.wait()

    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i",
                    "/workspace/out/notes_sketch_dark.mp4",
                    "-vf", "fps=12,scale=640:-2", "-loop", "0",
                    "/workspace/out/preview.gif"], check=True)
    print("done")


def specimen():
    """One frame with each glyph laid out for visual check."""
    rng = random.Random(7)
    mask = Image.new("L", (SS_W, SS_H), 0)
    d = ImageDraw.Draw(mask)
    lay = [
        (g_quarter(), 300, 700, 2.2), (g_eighth(), 620, 720, 2.2),
        (g_beamed(2, 1), 950, 740, 2.0), (g_beamed(2, 2), 1330, 760, 2.0),
        (g_beamed(3, 1), 1700, 780, 1.8), (g_clef(), 500, 500, 2.2),
        (g_sparkle(), 1500, 450, 2.5), (g_staff(), 1250, 380, 1.6),
    ]
    for glyph, x, y, s in lay:
        draw_glyph(d, glyph, x, y, 0, s, 1.0, 1.0, 0, 123)
    m = mask.resize((W, H), Image.LANCZOS)
    rgb = mask_to_rgb_on_bg(m)
    Image.fromarray(rgb).save("/workspace/out/specimen.png")
    print("specimen saved")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "specimen":
        os.makedirs("/workspace/out", exist_ok=True)
        specimen()
    else:
        main()
