#!/usr/bin/env python3
"""Build the 1200x630 Open Graph card + README preview."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageChops
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(ROOT, "tools", "fonts") + os.sep
serif = lambda s: ImageFont.truetype(F + "PlayfairDisplay.ttf", s)
italic = lambda s: ImageFont.truetype(F + "PlayfairDisplay-Italic.ttf", s)

W, H = 1200, 630

# Background with a radial plum glow.
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
cx, cy = W * 0.72, H * 0.46
r = np.sqrt(((xx - cx) / (W * 0.62)) ** 2 + ((yy - cy) / (H * 0.78)) ** 2)
r = np.clip(r, 0, 1)
base = np.zeros((H, W, 3), np.float32)
base[..., 0] = 9 + 26 * (1 - r) ** 2.2
base[..., 1] = 4 + 8 * (1 - r) ** 2.4
base[..., 2] = 9 + 20 * (1 - r) ** 2.2
img = Image.fromarray(base.astype(np.uint8), "RGB")

# Rose, screen-blended on the right.
rose = Image.open(os.path.join(ROOT, "assets", "rose-master.png")).convert("RGB")
rh = 760
rw = round(rh * rose.width / rose.height)
rose = rose.resize((rw, rh), Image.LANCZOS)
mask = Image.new("L", (rw, rh), 255)
md = ImageDraw.Draw(mask)
for x in range(int(rw * 0.34)):
    md.line([(x, 0), (x, rh)], fill=int(255 * (x / (rw * 0.34)) ** 0.85))
black = Image.new("RGB", (rw, rh), (0, 0, 0))
rose_masked = Image.composite(rose, black, mask)
layer = Image.new("RGB", (W, H), (0, 0, 0))
layer.paste(rose_masked, (W - rw + 40, (H - rh) // 2 - 10))
img = ImageChops.screen(img, layer)

d = ImageDraw.Draw(img)
d.text((82, 96), "A  B L O O M  F O R  A Y A", font=serif(17), fill=(255, 158, 203))
d.line([(82, 128), (168, 128)], fill=(255, 61, 154), width=2)

d.text((76, 158), "Rosa", font=serif(142), fill=(246, 238, 244))
d.text((76, 296), "Aya", font=italic(150), fill=(255, 158, 203))

d.text((82, 500), "One real rose. Ten seconds of bloom.", font=italic(27), fill=(185, 166, 181))
d.text((82, 537), "A name written in the light.", font=italic(27), fill=(185, 166, 181))

d.line([(82, 583), (620, 583)], fill=(255, 255, 255, 30), width=1)
d.text((82, 592), "FOR AYA  ·  GITHUB.COM/YOUSRIS/ROSA-AYA", font=serif(13), fill=(139, 116, 136))

# Vignette.
va = np.clip((np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.86)) ** 2) - 0.45) / 0.6, 0, 1) ** 1.6
va = (va * 150).astype(np.uint8)
vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
vig.putalpha(Image.fromarray(va))
img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")

os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
img.save(os.path.join(ROOT, "assets", "og.jpg"), "JPEG", quality=90, optimize=True, progressive=True)
img.save(os.path.join(ROOT, "docs", "preview.jpg"), "JPEG", quality=88, optimize=True, progressive=True)
print("wrote assets/og.jpg and docs/preview.jpg", img.size)
