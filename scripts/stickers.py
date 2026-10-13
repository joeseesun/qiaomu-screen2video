#!/usr/bin/env python3
"""Reaction stickers / memes for the motion plan.

Sources (resolved to a cached local file, then rendered into a short alpha clip):
  noto:1f389          Google Noto animated emoji (GIF, CC BY 4.0 → credits.txt)
  fluent:Party popper Microsoft Fluent Emoji 3D PNG (MIT)
  memegen:drake       memegen.link template (MIT code; template image rights are the user's call);
                      the caption is typeset locally so Chinese renders correctly
  file:assets/x.gif   any local PNG/GIF/WebP the user supplied

Animation: pop-in bounce (0→115%→96%→100% in ~0.32 s, slight tilt), gentle idle float,
scale-down fade-out. Clips are PNG-in-MOV with alpha, overlaid by FFmpeg below the subtitles.
"""
import hashlib
import math
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

CACHE = Path.home() / '.cache/qiaomu-screen2video/stickers'
UA = {'User-Agent': 'qiaomu-screen2video/1.0'}
CREDITS = {
    'noto': 'Noto Emoji Animation © Google, CC BY 4.0 (https://googlefonts.github.io/noto-emoji-animation/)',
    'fluent': 'Fluent Emoji © Microsoft, MIT (https://github.com/microsoft/fluentui-emoji)',
    'memegen': 'Meme template via memegen.link (https://github.com/jacebrowning/memegen)',
}


def _fetch(url, dest):
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if len(data) < 200:
        raise RuntimeError('贴纸下载内容异常: ' + url)
    tmp = dest.with_suffix(dest.suffix + '.part')
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def resolve(source, project):
    """Return (local_path, credit_or_None) for a sticker source string."""
    kind, _, value = source.partition(':')
    value = value.strip()
    if kind == 'noto':
        code = value.lower().replace('u+', '').replace(' ', '_')
        if not re.fullmatch(r'[0-9a-f_]{4,40}', code):
            raise ValueError('noto 贴纸需要 Unicode 码点，例如 noto:1f389 或 noto:1f602')
        return _fetch(f'https://fonts.gstatic.com/s/e/notoemoji/latest/{code}/512.gif', CACHE / 'noto' / f'{code}.gif'), CREDITS['noto']
    if kind == 'fluent':
        name = value
        snake = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        url = ('https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/'
               + urllib.parse.quote(name) + f'/3D/{snake}_3d.png')
        return _fetch(url, CACHE / 'fluent' / f'{snake}_3d.png'), CREDITS['fluent']
    if kind == 'memegen':
        template = value.strip('/')
        if not re.fullmatch(r'[a-z0-9_\-]{2,40}', template):
            raise ValueError('memegen 贴纸写模板 id，例如 memegen:drake；文字放 caption 字段')
        return _fetch(f'https://api.memegen.link/images/{template}.png', CACHE / 'memegen' / f'{template}.png'), CREDITS['memegen']
    if kind == 'file':
        path = (Path(project) / value).resolve()
        if not path.is_file():
            raise FileNotFoundError('贴纸文件不存在: ' + value)
        return path, None
    raise ValueError('贴纸来源需以 noto: / fluent: / memegen: / file: 开头')


def _frames(path):
    """RGBA frames with durations (seconds); still images become one long frame."""
    im = Image.open(path)
    out = []
    for frame in ImageSequence.Iterator(im):
        out.append((frame.convert('RGBA'), max(0.02, frame.info.get('duration', 40) / 1000)))
    return out or [(im.convert('RGBA'), 10.0)]


def _caption(img, text, font_path):
    """Meme caption: bold white with black stroke, bottom band, typeset locally (correct CJK)."""
    if not text:
        return img
    w, h = img.size
    draw = ImageDraw.Draw(img)
    size = max(18, int(h * 0.12))
    font = ImageFont.truetype(font_path, size)
    while draw.textlength(text, font=font) > w * 0.92 and size > 14:
        size -= 2
        font = ImageFont.truetype(font_path, size)
    tw = draw.textlength(text, font=font)
    draw.text(((w - tw) / 2, h - size * 1.35), text, font=font, fill='white',
              stroke_width=max(2, size // 10), stroke_fill='black')
    return img


def _ease_scale(t, dur):
    """Pop-in bounce, idle float, exit shrink. Returns (scale, alpha, dy_fraction)."""
    keys = [(0.0, 0.0), (0.14, 1.15), (0.24, 0.96), (0.32, 1.0)]
    if t < keys[-1][0]:
        for (t0, s0), (t1, s1) in zip(keys, keys[1:]):
            if t <= t1:
                u = (t - t0) / (t1 - t0)
                u = 1 - (1 - u) ** 2
                scale = s0 + (s1 - s0) * u
                break
    else:
        scale = 1.0
    alpha = min(1.0, t / 0.08)
    out = dur - t
    if out < 0.18:
        u = max(0.0, out / 0.18)
        scale *= 0.85 + 0.15 * u
        alpha *= u
    dy = 0.015 * math.sin(2 * math.pi * t / 1.6) if t > 0.32 else 0.0
    return scale, alpha, dy


def build_clip(path, out, seconds, fps, size_px, tilt=-4.0, caption=None, font_path=None):
    """Render the animated sticker to a PNG-in-MOV alpha clip of exactly `seconds`."""
    frames = _frames(path)
    if caption:
        frames = [(_caption(f.copy(), caption, font_path), d) for f, d in frames]
    w0, h0 = frames[0][0].size
    k = size_px / max(w0, h0)
    base_w, base_h = max(2, round(w0 * k)), max(2, round(h0 * k))
    canvas = int(math.ceil(max(base_w, base_h) * 1.25 / 2) * 2) + 8
    total = sum(d for _, d in frames)
    tmp = out.with_suffix('.frames')
    tmp.mkdir(parents=True, exist_ok=True)
    n = max(1, round(seconds * fps))
    cache = {}
    for i in range(n):
        t = i / fps
        # loop the source animation
        u = t % total if total > 0 else 0
        idx = 0
        while idx < len(frames) - 1 and u >= frames[idx][1]:
            u -= frames[idx][1]
            idx += 1
        scale, alpha, dy = _ease_scale(t, seconds)
        img = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
        if scale > 0.01 and alpha > 0.01:
            key = (idx, round(scale, 3))
            if key not in cache:
                sw, sh = max(1, round(base_w * scale)), max(1, round(base_h * scale))
                cache[key] = frames[idx][0].resize((sw, sh), Image.Resampling.LANCZOS).rotate(
                    tilt, resample=Image.Resampling.BICUBIC, expand=True)
                if len(cache) > 400:
                    cache.clear()
            sp = cache[key]
            if alpha < 1:
                sp = sp.copy()
                sp.putalpha(sp.getchannel('A').point(lambda a: int(a * alpha)))
            x = (canvas - sp.width) // 2
            y = (canvas - sp.height) // 2 + round(dy * canvas)
            img.alpha_composite(sp, (max(0, x), max(0, y)))
        img.save(tmp / f'{i:05d}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-i', str(tmp / '%05d.png'),
                    '-c:v', 'png', '-pix_fmt', 'rgba', str(out)], check=True)
    for f in tmp.glob('*.png'):
        f.unlink()
    tmp.rmdir()
    return canvas


def clip_key(source, caption, seconds, fps, size_px, tilt):
    return hashlib.sha256(f'{source}|{caption}|{seconds:.3f}|{fps}|{size_px}|{tilt}'.encode()).hexdigest()[:16]
