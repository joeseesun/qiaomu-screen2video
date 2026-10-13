#!/usr/bin/env python3
"""Fit a generated full-bleed background and typeset an accurate cover title."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT = Path.home()/'.cache/qiaomu-screen2video/fonts/NotoSansSC-Bold.ttf'
LIME = '#D9FF3F'

def font(size):
    if not FONT.is_file():
        raise FileNotFoundError('先运行 scripts/fonts.py')
    return ImageFont.truetype(FONT, size)

def shadow_text(draw, xy, text, fnt, fill, stroke):
    x, y = xy
    draw.text((x+max(3, fnt.size//35), y+max(4, fnt.size//28)), text, font=fnt,
              fill='#000000B8', stroke_width=stroke+2, stroke_fill='#00000080')
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke, stroke_fill='#090B0E')

def compose(background, output, size, layout, kicker='AI 改造 iOS', line1='一句话', line2='4 套设计', accent=LIME):
    w, h = size
    with Image.open(background) as src:
        base = ImageOps.fit(src.convert('RGB'), (w, h), Image.Resampling.LANCZOS).convert('RGBA')
    shade = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    if layout == 'vertical':
        sd.rectangle((0, 0, w, int(h*.27)), fill=(4, 7, 10, 145))
        shade = shade.filter(ImageFilter.GaussianBlur(max(8, w//80)))
        base.alpha_composite(shade)
        d = ImageDraw.Draw(base)
        over = font(round(w*.055)); big = font(round(w*.125)); stroke=max(3, round(w*.003))
        label=kicker; box=d.textbbox((0,0),label,font=over); x=(w-(box[2]-box[0]))//2
        shadow_text(d,(x,round(h*.055)),label,over,'#FFFFFF',max(2,stroke//2))
        box=d.textbbox((0,0),line1,font=big); x=(w-(box[2]-box[0]))//2
        shadow_text(d,(x,round(h*.105)),line1,big,'#FFFFFF',stroke)
        box=d.textbbox((0,0),line2,font=big); x=(w-(box[2]-box[0]))//2
        shadow_text(d,(x,round(h*.175)),line2,big,accent,stroke)
    else:
        sd.rectangle((0, 0, int(w*.46), h), fill=(3, 6, 9, 110))
        shade = shade.filter(ImageFilter.GaussianBlur(max(10, h//65)))
        base.alpha_composite(shade)
        d = ImageDraw.Draw(base)
        over=font(round(h*.044)); big=font(round(h*.118)); stroke=max(3,round(h*.0035)); x=round(w*.055)
        shadow_text(d,(x,round(h*.255)),kicker,over,'#FFFFFF',max(2,stroke//2))
        shadow_text(d,(x,round(h*.33)),line1,big,'#FFFFFF',stroke)
        shadow_text(d,(x,round(h*.455)),line2,big,accent,stroke)
    output.parent.mkdir(parents=True, exist_ok=True)
    base.convert('RGB').save(output, quality=95, subsampling=0)

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('background',type=Path); ap.add_argument('output',type=Path)
    ap.add_argument('--width',type=int,required=True); ap.add_argument('--height',type=int,required=True)
    ap.add_argument('--layout',choices=['intro','landscape','vertical'],required=True)
    ap.add_argument('--kicker',default='AI 改造 iOS',help='小标题'); ap.add_argument('--line1',default='一句话',help='主标题第一行')
    ap.add_argument('--line2',default='4 套设计',help='主标题第二行（强调色）'); ap.add_argument('--accent',default=LIME,help='强调色，如向阳朱 #F05A3C')
    a=ap.parse_args(); compose(a.background,a.output,(a.width,a.height),a.layout,a.kicker,a.line1,a.line2,a.accent)
