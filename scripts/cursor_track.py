#!/usr/bin/env python3
"""Track the mouse cursor in a screen recording by multi-scale template matching.

Why: clicks, ripples, spotlight boxes and any camera decision need to know where the pointer is.
What it is good at: the arrow cursor (including when the recorder itself has zoomed, because the
cursor then appears larger: the matched scale is reported).
What it cannot see: hand/I-beam cursors (they simply score low and are dropped).  Hand-cursor
positions must be read off a frame by eye.  UI-change heuristics for "click" detection also fire on
hover highlights and recorder zooms, so confirm clicks on frames before drawing anything.

Needs opencv-python-headless + numpy (see SKILL.md venv).

  cursor_track.py template SRC OUT.png --at 3 --box x,y,w,h   # cut the arrow out of one full-res frame
  cursor_track.py track SRC TEMPLATE.png OUT.json [--step 4]  # [t, score, scale, x, y] in source pixels
  cursor_track.py check SRC OUT.json --at 14,40,62             # draw the tracked point on frames
"""
from __future__ import annotations

import argparse
import json
import sys

SCALES = [0.55, 0.7, 0.85, 1.0, 1.2, 1.45, 1.75, 2.1]


def _cv():
    import cv2
    import numpy as np
    return cv2, np


def grab_frame(src, t):
    cv2, _ = _cv()
    cap = cv2.VideoCapture(src)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, fr = cap.read()
    if not ok:
        raise SystemExit(f"cannot read frame at {t}s")
    return fr


def make_template(src, out, at, box):
    cv2, _ = _cv()
    x, y, w, h = box
    fr = grab_frame(src, at)
    cv2.imwrite(out, fr[y:y + h, x:x + w])
    print("template", out, fr.shape, box)


def track(src, template, out, step=4, half=0.5, min_score=0.0):
    cv2, np = _cv()
    tpl = cv2.imread(template, cv2.IMREAD_GRAYSCALE)
    if tpl is None:
        raise SystemExit(f"cannot read template {template}")
    tpl = cv2.resize(tpl, None, fx=half, fy=half, interpolation=cv2.INTER_AREA)
    tpls = [(s, cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)) for s in SCALES]
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    rows, i = [], 0
    while cap.grab():
        if i % step == 0:
            ok, fr = cap.retrieve()
            g = cv2.cvtColor(cv2.resize(fr, None, fx=half, fy=half, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            best = (-1.0, 1.0, 0, 0)
            for s, t in tpls:
                r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                _, mx, _, loc = cv2.minMaxLoc(r)
                if mx > best[0]:
                    best = (mx, s, loc[0], loc[1])
            mx, s, x, y = best
            if mx >= min_score:
                # top-left of the template box is the arrow tip area; report in source pixels
                rows.append([round(i / fps, 3), round(float(mx), 3), s, int((x + 3 * s) / half), int((y + 3 * s) / half)])
        i += 1
    json.dump(rows, open(out, "w"))
    print(f"{len(rows)} samples -> {out}")


def clean(rows, min_score=0.82, jump_px=900, jump_score=0.95):
    """Keep confident arrow hits, drop teleports.  Returns [(t, x, y, scale)]."""
    keep = []
    for k, (t, sc, s, x, y) in enumerate(rows):
        if sc < min_score:
            continue
        if keep and abs(((x - keep[-1][1]) ** 2 + (y - keep[-1][2]) ** 2) ** 0.5) > jump_px and sc < jump_score:
            continue
        keep.append((t, x, y, s))
    return keep


def check(src, rows_path, times):
    cv2, _ = _cv()
    rows = json.load(open(rows_path))
    cap = cv2.VideoCapture(src)
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        r = min(rows, key=lambda o: abs(o[0] - t))
        cv2.circle(fr, (r[3], r[4]), 40, (0, 0, 255), 8)
        out = f"check_{t:g}.jpg"
        cv2.imwrite(out, cv2.resize(fr, None, fx=0.4, fy=0.4))
        print(out, "score", r[1], "scale", r[2])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("template"); a.add_argument("src"); a.add_argument("out"); a.add_argument("--at", type=float, required=True)
    a.add_argument("--box", required=True, help="x,y,w,h in source pixels")
    b = sub.add_parser("track"); b.add_argument("src"); b.add_argument("template"); b.add_argument("out")
    b.add_argument("--step", type=int, default=4); b.add_argument("--half", type=float, default=0.5)
    c = sub.add_parser("check"); c.add_argument("src"); c.add_argument("rows"); c.add_argument("--at", required=True)
    n = ap.parse_args(argv)
    if n.cmd == "template":
        make_template(n.src, n.out, n.at, [int(v) for v in n.box.split(",")])
    elif n.cmd == "track":
        track(n.src, n.template, n.out, n.step, n.half)
    else:
        check(n.src, n.rows, [float(v) for v in n.at.split(",")])


if __name__ == "__main__":
    sys.exit(main())
