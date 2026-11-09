#!/usr/bin/env python3
"""Render a cinematic 10s rose-bloom film from the still image."""
import math
import os
import shutil
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH = os.path.join(ROOT, "assets", "rose-master.png")
OUT_DIR = "/tmp/aya-bloom-frames"
FONT_ITALIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "PlayfairDisplay-Italic.ttf")

W, H = 1080, 1440
FPS = 30
DUR = 10.0
N = int(FPS * DUR)
CAM_D = 2.7

os.makedirs(OUT_DIR, exist_ok=True)
for f in os.listdir(OUT_DIR):
    if f.endswith(".png"):
        os.remove(os.path.join(OUT_DIR, f))

src = Image.open(SRC_PATH).convert("RGB")
sw, sh = src.size

# ------------------------------------------------------------------ helpers
def smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)

def perspective_coeffs(theta, phi, zoom, tx, ty):
    """Homography mapping output pixels -> source pixels for a rotated plane."""
    cy, sy = math.cos(theta), math.sin(theta)
    cx, sx = math.cos(phi), math.sin(phi)
    Ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]])
    R = Rx @ Ry

    # normalized plane coords (u, v) -> output pixels, with perspective
    row0 = np.array([
        H * zoom * CAM_D * R[0, 0] - (W / 2 + tx) * R[2, 0],
        H * zoom * CAM_D * R[0, 1] - (W / 2 + tx) * R[2, 1],
        (W / 2 + tx) * CAM_D,
    ])
    row1 = np.array([
        H * zoom * CAM_D * R[1, 0] - (H / 2 + ty) * R[2, 0],
        H * zoom * CAM_D * R[1, 1] - (H / 2 + ty) * R[2, 1],
        (H / 2 + ty) * CAM_D,
    ])
    row2 = np.array([-R[2, 0], -R[2, 1], CAM_D])
    Hn = np.vstack([row0, row1, row2])

    # source pixels -> normalized plane coords
    N = np.array([
        [1.0 / sh, 0.0, -sw / (2.0 * sh)],
        [0.0, 1.0 / sh, -sh / (2.0 * sh)],
        [0.0, 0.0, 1.0],
    ])
    Hf = Hn @ N
    Hi = np.linalg.inv(Hf)
    Hi /= Hi[2, 2]
    return list(Hi[0]) + list(Hi[1]) + [Hi[2, 0], Hi[2, 1]]

# ------------------------------------------------------------------ plates
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
cx, cy = W / 2.0, H * 0.455

# background: deep plum radial
bgr = np.sqrt(((xx - cx) / (W * 0.78)) ** 2 + ((yy - cy) / (H * 0.72)) ** 2)
bgr = np.clip(bgr, 0, 1)
bg_np = np.zeros((H, W, 3), dtype=np.float32)
for i, c in enumerate((16, 7, 16)):
    bg_np[..., i] = c * (1.0 - bgr) ** 1.7

# halo / core glow plates
halo_r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
halo = np.exp(-((halo_r / (0.42 * H)) ** 2)).astype(np.float32)
core = np.exp(-((halo_r / (0.105 * H)) ** 2)).astype(np.float32)
halo_np = np.stack([halo * 190, halo * 45, halo * 110], axis=-1)
core_np = np.stack([core * 255, core * 205, core * 230], axis=-1)

# specular sweep coordinate
sweep_coord = xx + 0.38 * yy

# vignette overlay
vr = np.sqrt(((xx - W / 2) / (W * 0.78)) ** 2 + ((yy - H / 2) / (H * 0.78)) ** 2)
va = (np.clip((vr - 0.52) / 0.58, 0, 1) ** 1.5 * 170).astype(np.uint8)
vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
vignette.putalpha(Image.fromarray(va))

# particle sprites
def make_sprite(size=36, color=(255, 176, 212)):
    s = np.linspace(-1, 1, size, dtype=np.float32)
    sx, sy = np.meshgrid(s, s)
    r = np.sqrt(sx * sx + sy * sy)
    a = np.exp(-(r * 2.3) ** 2)
    a = np.clip(a, 0, 1)
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    rgba[..., 0] = color[0]
    rgba[..., 1] = color[1]
    rgba[..., 2] = color[2]
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")

sprite_small = make_sprite(24)
sprite_mid = make_sprite(36)
sprite_big = make_sprite(52)

rng = np.random.default_rng(11)
PCOUNT = 64
particles = [{
    "x": rng.uniform(0, W),
    "y": rng.uniform(0, H),
    "vy": rng.uniform(8, 30),
    "vx": rng.uniform(-6, 6),
    "amp": rng.uniform(6, 24),
    "phase": rng.uniform(0, 2 * math.pi),
    "tw": rng.uniform(0.6, 1.8),
    "alpha": rng.uniform(0.10, 0.52),
    "sprite": [sprite_small, sprite_mid, sprite_big][int(rng.integers(0, 3))],
} for _ in range(PCOUNT)]

# text
font_text = ImageFont.truetype(FONT_ITALIC, 47)
text = "for aya"
tracking = 17
tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
text_w = sum(tmp.textlength(ch, font=font_text) for ch in text) + tracking * (len(text) - 1)
text_x = (W - text_w) / 2.0
text_y = H - 118

# ------------------------------------------------------------------ frames
print(f"Rendering {N} frames at {W}x{H} ...", flush=True)
for i in range(N):
    t = i / FPS
    e = smoothstep(min(t / 3.8, 1.0))          # bloom progress
    fade = smoothstep(min(t / 0.8, 1.0)) * (1.0 - smoothstep(max((t - 9.15) / 0.85, 0.0)))

    theta = math.radians(7.2) * math.sin(t * 0.55 - 0.55)
    phi = math.radians(2.4) * math.sin(t * 0.43 + 0.9)
    zoom = 1.035 + 0.055 * e + 0.006 * math.sin(t * 0.7)
    ty = (1.0 - e) * 26.0

    coeffs = perspective_coeffs(theta, phi, zoom, 0.0, ty)
    rose = src.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(0, 0, 0))
    rose_np = np.asarray(rose).astype(np.float32)

    # bloom mask radiating from the heart of the rose
    outer = (0.10 + 1.06 * e) * H
    inner = outer * 0.52
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = np.clip((outer - dist) / max(outer - inner, 1.0), 0, 1)
    mask = mask * mask * (3 - 2 * mask)
    bright = (0.45 + 0.55 * e) * fade
    rose_np *= (mask * bright)[..., None]

    # specular sweep across the petals
    sweep_center = (-0.35 + 1.55 * (t / DUR)) * W
    band = np.exp(-((sweep_coord - sweep_center) ** 2) / (2 * (0.12 * W) ** 2))
    rose_np += rose_np * (band * 0.5 * e)[..., None]
    np.clip(rose_np, 0, 255, out=rose_np)

    # screen the rose over the dark background
    frame_np = 255.0 - (255.0 - bg_np) * (255.0 - rose_np) / 255.0

    # glow
    gi = (0.10 + 0.14 * e) * fade
    ci = (0.28 + 0.18 * e + 0.05 * math.sin(t * 1.9)) * fade
    frame_np += halo_np * gi
    frame_np += core_np * ci
    np.clip(frame_np, 0, 255, out=frame_np)
    frame = Image.fromarray(frame_np.astype(np.uint8), "RGB").convert("RGBA")

    # dust
    pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for p in particles:
        py = p["y"] - t * p["vy"]
        px = p["x"] + math.sin(t * p["tw"] + p["phase"]) * p["amp"] + t * p["vx"]
        py = py % (H + 80) - 40
        px = px % (W + 80) - 40
        alpha = p["alpha"] * fade * (0.55 + 0.45 * math.sin(t * 1.5 + p["phase"]))
        if alpha <= 0.01:
            continue
        sp = p["sprite"]
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * alpha)))
        pl.paste(sp, (int(px), int(py)), sp)
    frame = Image.alpha_composite(frame, pl)
    frame = Image.alpha_composite(frame, vignette)

    # dedication
    ta = smoothstep((t - 6.35) / 0.9) * (1.0 - smoothstep((t - 9.02) / 0.75))
    if ta > 0.01:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        col = (255, 178, 211, int(225 * ta))
        d.line([(W / 2 - 40, text_y - 30), (W / 2 + 40, text_y - 30)],
               fill=(255, 158, 203, int(90 * ta)), width=1)
        x = text_x
        for ch in text:
            d.text((x, text_y), ch, font=font_text, fill=col)
            x += d.textlength(ch, font=font_text) + tracking
        frame = Image.alpha_composite(frame, ov)

    frame.convert("RGB").save(os.path.join(OUT_DIR, f"frame_{i:04d}.png"))

    if i % 30 == 0:
        print(f"  {i}/{N}", flush=True)

print("Encoding ...", flush=True)
mp4 = os.path.join(ROOT, "assets", "rose-bloom.mp4")
subprocess.run([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
    "-framerate", str(FPS), "-i", os.path.join(OUT_DIR, "frame_%04d.png"),
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow",
    "-movflags", "+faststart", "-an", mp4,
], check=True)

# poster from a fully bloomed frame
poster = Image.open(os.path.join(OUT_DIR, "frame_0180.png")).convert("RGB")
poster.save(os.path.join(ROOT, "assets", "rose-bloom-poster.jpg"), "JPEG", quality=90, optimize=True)

print("done", os.path.getsize(mp4), "bytes")
