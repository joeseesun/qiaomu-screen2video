#!/usr/bin/env python3
"""Editorial-plate look: reusable ASS building blocks (Vercel x New Yorker).

Everything is expressed in a 1920x1080 script space; libass scales it to any output size
(1080p or 4K) so one script renders both.  See references/editorial-plate.md for the design
rules and references/examples/rss-audio/build.py for a complete build that uses the same ideas.

Public pieces:
  ease_out_expo / ease_out_spring / ease_in_cubic   motion tokens
  Ass                                               event collector; eases text in automatically
  rounded_rect / rect / circle                      ASS drawing paths
  karaoke_line                                      one line lit word by word
  chapter_progress                                  segmented thin progress line + centred dot + labels
  detached_card                                     opaque rounded intro card with eased rise
  cold_open_karaoke                                 giant-type opener synced to the voice
  outro_search                                      "search in the plugin market" end card
"""
from __future__ import annotations

import math
import re

SCRIPT_INTERFACE = "internal-module"   # imported by build scripts; `python3 editorial_ass.py` prints a demo ASS

PLAY_W, PLAY_H = 1920, 1080
FPS = 30

# ---- palette: a parameter, not a fixed look -------------------------------------------------
from dataclasses import dataclass


def _bgr(hex_rgb: str) -> str:
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}&".upper().replace("&H", "&H")


@dataclass(frozen=True)
class Palette:
    """What stays fixed across looks is the structure (hierarchy, spacing, motion, ONE accent).
    What varies per video is the skin: accent colour, canvas, card tone.  Pick per topic and
    show 3 candidate still frames before rendering (see references/editorial-plate.md)."""
    name: str = "mono-blue"
    ink: str = "&H000000&"            # canvas on the video plate, text on paper pages
    paper: str = "&HFFFFFF&"          # opener / outro page
    accent_dark: str = "&HFF9132&"    # accent used on the dark canvas
    accent_light: str = "&HF37000&"   # accent used on the paper pages
    text: str = "&HD4D4D4&"           # subtitle base on the dark canvas
    en: str = "&HB4B4B4&"
    dim: str = "&H777777&"
    hair: str = "&H333333&"
    card: str = "&H0A0A0A&"
    card_border: str = "&H4A4A4A&"
    white: str = "&HFFFFFF&"
    unsung: str = "&HDCDCDC&"         # karaoke text before it is spoken


def palette_from_hex(accent: str, name: str = "custom", *, accent_on_paper: str | None = None, **overrides) -> Palette:
    """Build a palette from one accent colour, e.g. palette_from_hex("#7C5CFF").  accent_on_paper lets the
    accent be darker on white pages; neutrals stay black/white unless overridden."""
    return Palette(name=name, accent_dark=_bgr(accent), accent_light=_bgr(accent_on_paper or accent), **overrides)


PALETTES = {
    "mono-blue": Palette(),                                                    # Vercel-like; used for the RSS video
    "mono-vermilion": palette_from_hex("#F05A3C", "mono-vermilion"),           # 乔木 brand colour
    "mono-violet": palette_from_hex("#8B7CFF", "mono-violet", accent_on_paper="#6D4AFF"),   # close to Obsidian purple
    "mono-emerald": palette_from_hex("#34D399", "mono-emerald", accent_on_paper="#0E9F6E"),
    "mono-none": palette_from_hex("#FFFFFF", "mono-none", accent_on_paper="#000000"),       # no accent at all
}

# Back-compat module constants = the default palette
INK, PAPER = PALETTES["mono-blue"].ink, PALETTES["mono-blue"].paper
ACC_DARK, ACC_LIGHT = PALETTES["mono-blue"].accent_dark, PALETTES["mono-blue"].accent_light
GRAY_TEXT, GRAY_EN, DIM, HAIR, WHITE = (PALETTES["mono-blue"].text, PALETTES["mono-blue"].en,
                                        PALETTES["mono-blue"].dim, PALETTES["mono-blue"].hair, PALETTES["mono-blue"].white)

# ---- motion tokens ------------------------------------------------------------------------
def ease_out_expo(u: float) -> float:
    """Fast attack, soft landing: 1 - 2^(-10u).  Use for everything that enters."""
    return 1.0 if u >= 1 else 1 - 2 ** (-10 * max(u, 0.0))


def ease_out_spring(u: float, overshoot: float = 0.045) -> float:
    """expo-out with a small overshoot; keep the overshoot under 6% or it reads as wobble."""
    if u >= 1:
        return 1.0
    e = ease_out_expo(u)
    return e + overshoot * math.sin(math.pi * u) * (1 - u) * 2.2


def ease_in_cubic(u: float) -> float:
    """Exits accelerate away: u^3.  Exits are shorter than entrances."""
    return min(max(u, 0.0), 1.0) ** 3


def ts(t: float) -> str:
    t = max(t, 0.0)
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ---- drawings -----------------------------------------------------------------------------
def rect(w: float, h: float) -> str:
    return f"m 0 0 l {w:g} 0 l {w:g} {h:g} l 0 {h:g}"


def rounded_rect(w: float, h: float, r: float) -> str:
    k = 0.5523 * r
    return (f"m {r:g} 0 l {w-r:g} 0 b {w-r+k:.1f} 0 {w:g} {r-k:.1f} {w:g} {r:g} l {w:g} {h-r:g} "
            f"b {w:g} {h-r+k:.1f} {w-r+k:.1f} {h:g} {w-r:g} {h:g} l {r:g} {h:g} "
            f"b {r-k:.1f} {h:g} 0 {h-r+k:.1f} 0 {h-r:g} l 0 {r:g} b 0 {r-k:.1f} {r-k:.1f} 0 {r:g} 0")


def circle(r: float) -> str:
    """Circle with a positive-coordinate path (0..2r).  Draw it with \\an7 and subtract r from the
    target centre.  Paths with negative coordinates drift off-centre under \\an5 in libass."""
    k = 0.5523 * r
    d = 2 * r
    return (f"m 0 {r:g} b 0 {r-k:.1f} {r-k:.1f} 0 {r:g} 0 b {r+k:.1f} 0 {d:g} {r-k:.1f} {d:g} {r:g} "
            f"b {d:g} {r+k:.1f} {r+k:.1f} {d:g} {r:g} {d:g} b {r-k:.1f} {d:g} 0 {r+k:.1f} 0 {r:g}")


# ---- styles -------------------------------------------------------------------------------
def style(name, font, size, primary, *, secondary=None, outline="&H00000000&", bold=0, italic=0,
          align=5, spacing=0.0, border_style=1, outline_w=0, shadow=0):
    sec = secondary or primary
    return (f"Style: {name},{font},{size},{primary},{sec},{outline},&H00000000&,{bold},{italic},0,0,"
            f"100,100,{spacing},0,{border_style},{outline_w},{shadow},{align},0,0,0,1")


def default_styles(sans="LXGW Neo XiHei", serif="Songti SC", mono="Menlo",
                   en="Atkinson Hyperlegible Next SemiBold", did="Didot", pal: Palette | None = None):
    pal = pal or PALETTES["mono-blue"]
    """Menlo has no CJK glyphs: any mono-styled line that contains Chinese must override \\fn with the sans."""
    return [
        style("Sub", sans, 52, pal.text, spacing=0.5),
        style("Quote", serif, 52, pal.paper),                       # lines the product reads aloud
        style("En", en, 34, pal.en, spacing=0.2),
        style("Karaoke", serif, 198, pal.ink, secondary=pal.unsung, bold=1, align=7),
        style("Lbl", sans, 20, pal.dim, spacing=0.5, align=4),
        style("Dr", sans, 20, pal.white, align=7),
        style("Serif", serif, 60, pal.ink, bold=1),
        style("Did", did, 44, pal.ink, italic=1),
        style("Mono", mono, 22, pal.ink, spacing=4),
        style("Sans", sans, 30, pal.ink),
    ]


HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
{styles}
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

# style -> (rise distance px, duration s).  Text in these styles eases in on its own.
RISE = {"Sub": (10, 0.16), "Quote": (10, 0.16), "En": (10, 0.18), "Serif": (22, 0.42), "Did": (16, 0.42)}

_POS = re.compile(r"\\pos\((-?[\d.]+),(-?[\d.]+)\)")
_FAD = re.compile(r"\\fad\((\d+),(\d+)\)")
_A1 = re.compile(r"\\1a&H([0-9A-Fa-f]{2})&")


class Ass:
    def __init__(self, styles=None, play=(PLAY_W, PLAY_H), fps=FPS, palette: Palette | str | None = None):
        self.pal = PALETTES[palette] if isinstance(palette, str) else (palette or PALETTES["mono-blue"])
        self.styles = styles or default_styles(pal=self.pal)
        self.play = play
        self.fps = fps
        self.events: list[str] = []

    # -- raw line
    def line(self, a, b, st, text, layer=1):
        self.events.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{st},,0,0,0,,{text}")

    # -- text that carries \pos and \fad(in,out) in a RISE style rises + fades in on the expo curve
    def add(self, a, b, st, text, layer=1):
        m, f = _POS.search(text), _FAD.search(text)
        if st in RISE and m and f and text.startswith("{") and b - a > 0.25:
            x, y = float(m.group(1)), float(m.group(2))
            fade_out = int(f.group(2)) / 1000
            dy, dur = RISE[st]
            body = text.replace(m.group(0), "").replace(f.group(0), "")
            j = body.index("}")
            tags, txt = body[1:j], body[j + 1:]
            orig = _A1.search(tags)
            base_alpha = int(orig.group(1), 16) if orig else 0
            tags_plain = _A1.sub("", tags)
            n = max(1, int(dur * self.fps))
            for k in range(n):
                u = (k + 1) / n
                e = ease_out_expo(u)
                t0, t1 = a + k / self.fps, min(a + (k + 1) / self.fps, b)
                if t0 >= b:
                    break
                al = max(base_alpha, int(255 * (1 - min(1, e * 1.25))))
                self.line(t0, t1, st, "{" + f"\\pos({x:.1f},{y + dy * (1 - e):.1f})\\1a&H{al:02X}&" + tags_plain + "}" + txt, layer)
            hold0, hold1 = a + n / self.fps, b - fade_out
            if hold1 > hold0:
                self.line(hold0, hold1, st, "{" + f"\\pos({x:.1f},{y})" + tags + "}" + txt, layer)
            if fade_out > 0:
                self.line(max(hold0, hold1), b, st,
                          "{" + f"\\pos({x:.1f},{y})\\fad(0,{int(fade_out * 1000)})" + tags + "}" + txt, layer)
            return
        self.line(a, b, st, text, layer)

    def shape(self, a, b, x, y, path, color, alpha="00", layer=10, extra=""):
        self.line(a, b, "Dr", f"{{\\an7\\pos({x},{y})\\c{color}\\1a&H{alpha}&\\bord0\\shad0{extra}\\p1}}{path}{{\\p0}}", layer)

    def render(self) -> str:
        return HEADER.format(w=self.play[0], h=self.play[1], styles="\n".join(self.styles)) + "\n".join(self.events) + "\n"


# ---- karaoke ------------------------------------------------------------------------------
def karaoke_line(parts, start=0.0):
    """parts: [(text, t0, t1), ...] in seconds on the same clock as `start`.  Returns tagged text.
    Unsung text shows in SecondaryColour, sung text in PrimaryColour.  Gaps become blank \\k."""
    out, cur = "", start
    for tx, s_, e_ in parts:
        gap = max(0, round((s_ - cur) * 100))
        if gap:
            out += "{\\k%d}" % gap
        out += "{\\kf%d}%s" % (max(1, round((e_ - s_) * 100)), tx)
        cur = e_
    return out


def cold_open_karaoke(ass: Ass, duration, lines, english, footer_left, footer_right, left=160):
    """lines: [(y, parts), ...] (3 lines of ~200px type fill the frame).  Only this sentence, an English
    gloss and a footer: no kicker, no deck, no glow.  Page fades out over the last 0.3 s."""
    ass.shape(0, duration, 0, 0, rect(PLAY_W, PLAY_H), ass.pal.paper, "00", 40, "\\fad(0,300)")
    for y, parts in lines:
        ass.line(0, duration, "Karaoke", "{\\an4\\fad(200,300)\\pos(%d,%d)}" % (left - 10, y) + karaoke_line(parts), 42)
    ass.add(0.2, duration, "En", "{\\an4\\fad(300,300)\\fs36\\pos(%d,940)}%s" % (left, english), 42)
    ass.add(0.2, duration, "Sans", "{\\an4\\fad(300,300)\\fs22\\pos(%d,1010)\\1a&H60&}%s" % (left, footer_left), 42)
    ass.add(0.2, duration, "Sans", "{\\an6\\fad(300,300)\\fs22\\pos(%d,1010)\\1a&H60&}%s" % (PLAY_W - left, footer_right), 42)


# ---- chapter progress ---------------------------------------------------------------------
def chapter_progress(ass: Ass, bounds, names, x0, width, *, line_y=1058, label_y=1030, gap=8, t_end=None,
                     prop=0.4):
    """Thin segmented line.  bounds = N+1 times; each segment gets `prop` of its width from its duration
    and the rest equally (so a 5 s chapter still fits its label).  The dot is centred on the line."""
    n = len(names)
    t_end = bounds[-1] if t_end is None else t_end
    span = bounds[-1] - bounds[0]
    usable = width - gap * (n - 1)
    widths = [usable * (prop * (bounds[i + 1] - bounds[i]) / span + (1 - prop) / n) for i in range(n)]
    x = x0
    dot = circle(6)
    pal = ass.pal
    for i, (name, w) in enumerate(zip(names, widths)):
        xi, wi = round(x), round(w)
        a, b = bounds[i], bounds[i + 1]
        dur = int((b - a) * 1000)
        ass.shape(bounds[0], t_end, xi, line_y - 2, rect(wi, 4), pal.hair, "00", 9, "\\fad(300,300)")
        ass.line(a, t_end, "Dr", f"{{\\an7\\pos({xi},{line_y - 2})\\c{pal.white}\\bord0\\shad0\\fscx0\\t(0,{dur},\\fscx100)\\p1}}{rect(wi, 4)}{{\\p0}}", 10)
        ass.line(a, b, "Dr", f"{{\\an7\\move({xi - 6},{line_y - 6},{xi + wi - 6},{line_y - 6},0,{dur})\\c{pal.accent_dark}\\3c{pal.ink}\\bord2\\shad0\\fad(120,150)\\p1}}{dot}{{\\p0}}", 12)
        lab = f"{{\\fnMenlo\\fs21}}{i + 1:02d}{{\\fnLXGW Neo XiHei\\fs25}}   {name}"
        ass.line(bounds[0], t_end, "Lbl", f"{{\\an4\\pos({xi},{label_y})\\c{pal.dim}\\fad(300,300)}}" + lab, 11)
        ass.line(a, t_end, "Lbl", f"{{\\an4\\pos({xi},{label_y})\\c{pal.white}\\fad(150,0)}}" + lab, 12)
        x += w + gap
    return widths


# ---- detached intro card ------------------------------------------------------------------
def detached_card(ass: Ass, start, end, x, y, number, title, desc, *, w=540, h=164, enter=0.32, exit_=0.22):
    """Opaque, rounded, inset from the plate edge, hairline border + soft shadow.  Rises 14 px and fades in
    on the expo curve, children staggered 30/60/100 ms; exits faster, with the cubic-in curve.
    Never translucent (UI shows through and the type turns grey) and never fused to the plate edge."""
    fr = 1 / ass.fps

    def vis(t):
        if t < start or t >= end:
            return 0.0, 0.0
        if t < start + enter:
            e = ease_out_expo((t - start) / enter)
            return min(1, e * 1.2), 14 * (1 - e)
        if t > end - exit_:
            u = (t - (end - exit_)) / exit_
            return 1 - u, -8 * ease_in_cubic(u)
        return 1.0, 0.0

    def layer(kind, px, py, body, lay, base=0, delay=0.0):
        t = start
        while t < end - 1e-6:
            v, dy = vis(t - delay if t - delay >= start else start - 1)
            if t < start + enter + delay or t >= end - exit_:
                t0, t1, t = t, min(t + fr, end), t + fr
            else:
                t0, t1, v, dy = t, end - exit_, 1.0, 0.0
                t = end - exit_
            al = int(255 - (255 - base) * v)
            tag = f"\\pos({px},{py + dy:.1f})\\1a&H{al:02X}&"
            if kind == "shape":
                ass.line(t0, t1, "Dr", f"{{\\an7{tag}\\c{body[1]}\\bord0\\shad0{body[2]}\\p1}}{body[0]}{{\\p0}}", lay)
            else:
                ass.line(t0, t1, body[0], f"{{\\an4{tag}{body[1]}}}{body[2]}", lay)

    pal = ass.pal
    layer("shape", x, y + 10, (rounded_rect(w, h, 16), "&H000000&", "\\blur14"), 13, 0x78)
    layer("shape", x - 1, y - 1, (rounded_rect(w + 2, h + 2, 17), pal.card_border, ""), 14)
    layer("shape", x, y, (rounded_rect(w, h, 16), pal.card, ""), 15)
    layer("text", x + 30, y + 34, ("Mono", f"\\fs22\\c{pal.accent_dark}", number), 16, 0, 0.03)
    layer("text", x + 30, y + 86, ("Serif", f"\\fs50\\b1\\c{pal.white}", title), 16, 0, 0.06)
    layer("text", x + 30, y + 136, ("Sans", f"\\fs23\\c&HB5B5B5&", desc), 16, 0, 0.10)


# ---- outro --------------------------------------------------------------------------------
def outro_search(ass: Ass, t0, total, query, card_title, card_desc, name, accounts, left=160):
    """White page: headline, a search field that types `query`, the plugin card with an Install button,
    and a right column with the author and accounts."""
    pal = ass.pal
    ass.shape(t0, total, 0, 0, rect(PLAY_W, PLAY_H), pal.paper, "00", 40, "\\fad(500,0)")
    ass.shape(t0 + 0.4, total, left, 96, rect(1600, 1), pal.ink, "00", 41, "\\fad(300,0)")
    ass.add(t0 + 0.5, total, "Mono", "{\\an4\\fad(300,0)\\pos(%d,138)\\1a&H40&}OBSIDIAN  —  COMMUNITY PLUGINS" % left, 42)
    ass.add(t0 + 0.6, total, "Serif", "{\\an4\\fad(350,0)\\fs128\\pos(%d,290)}去插件市场，搜索" % (left - 10), 42)
    for yy, hh, st, lay in ((400, 104, t0 + 0.9, 42), (540, 176, t0 + 3.2, 42)):
        ass.line(st, total, "Dr", f"{{\\an7\\pos({left},{yy})\\c&HFFFFFF&\\3c{pal.ink}\\bord1.5\\shad0\\fad(300,0)\\p1}}{rect(1100, hh)}{{\\p0}}", lay)
    ass.line(t0 + 1.1, t0 + 1.7, "Sans", "{\\an4\\pos(200,452)\\fs34\\1a&H80&\\fad(150,0)}Search community plugins…", 43)
    for k in range(1, len(query) + 1):
        a = t0 + 1.7 + 0.14 * (k - 1)
        b = t0 + 1.7 + 0.14 * k if k < len(query) else total
        ass.line(a, b, "Sans", "{\\an4\\pos(200,452)\\fs44}" + query[:k] + ("{\\c" + pal.accent_light + "}|" if k < len(query) else ""), 43)
    c0 = t0 + 3.2
    ass.add(c0, total, "Serif", "{\\fad(350,0)\\an4\\pos(200,596)\\fs46}" + card_title, 43)
    ass.line(c0, total, "Sans", "{\\fad(350,0)\\an4\\pos(200,660)\\fs26\\1a&H60&}" + card_desc, 43)
    ass.shape(c0 + 0.2, total, 1060, 590, rect(170, 62), pal.ink, "00", 43, "\\fad(350,0)")
    ass.line(c0 + 0.2, total, "Sans", "{\\fad(350,0)\\pos(1145,621)\\c" + pal.paper + "\\fs28}安装", 44)
    a = t0 + 4.2
    ass.shape(a, total, 1370, 400, rect(1, 316), pal.ink, "00", 41, "\\fad(300,0)")
    ass.add(a, total, "Serif", "{\\an4\\fad(400,0)\\fs52\\pos(1420,440)}" + name, 42)
    for j, tx in enumerate(accounts):
        ass.line(a + 0.15 + 0.1 * j, total, "Mono" if tx.isascii() else "Sans",
                 "{\\an4\\fad(400,0)\\fs26\\pos(1420,%d)\\1a&H20&}%s" % (520 + 54 * j, tx), 42)
    ass.shape(total - 0.7, total, 0, 0, rect(PLAY_W, PLAY_H), pal.ink, "00", 90, "\\fad(700,0)")


if __name__ == "__main__":  # tiny demo: python3 editorial_ass.py > demo.ass
    a = Ass()
    a.add(0.5, 3.0, "Sub", "{\\fad(70,70)\\pos(960,912)}你好，世界")
    print(a.render())
