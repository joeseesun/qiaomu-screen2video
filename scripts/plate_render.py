#!/usr/bin/env python3
"""Render the "plate": the recording cropped to 16:9, resized once with INTER_AREA, optional click ripples.

The plate is the only place the recording's pixels are touched.  Rules that came out of real use:
  * The recorder (Screen Studio, Camtasia...) usually already zooms.  Do NOT add a second camera on top:
    two cameras fighting makes the picture sway.  This script has no zoom on purpose.
  * Ripples are drawn in source coordinates, so they stay on the UI element.  Draw only clicks you have
    confirmed on a frame (hover highlights and recorder zooms look like clicks to heuristics).
  * Render at 2x the 1080p layout (e.g. 2972x1672 plate on a 3840x2160 canvas) when the source is wider
    than 2000 px; the UI text gains less than the overlay edges do (measure with a real-pixel crop).

  plate_render.py SRC OUT.mp4 --crop 172:1987 --size 1486x836 [--out-fps 30] [--click t:x:y ...]
  (--click x,y are in OUTPUT plate pixels)
"""
from __future__ import annotations

import argparse
import subprocess


def render(src, out, y0, y1, size, out_fps, clicks, crf=10, preset="veryfast"):
    import cv2
    ow, oh = size
    cap = cv2.VideoCapture(src)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 60
    every = max(1, round(src_fps / out_fps))
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}",
                           "-r", str(out_fps), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                           "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    i = n = 0
    k = ow / 1486  # ripple geometry is authored for a 1486 px plate
    while cap.grab():
        if i % every == 0:
            ok, fr = cap.retrieve()
            frame = cv2.resize(fr[y0:y1, :], (ow, oh), interpolation=cv2.INTER_AREA)
            t = n / out_fps
            for tc, x, y in clicks:
                u = (t - tc) / 0.65
                if 0 <= u < 1:
                    e = 1 - 2 ** (-10 * u)
                    ov = frame.copy()
                    cv2.circle(ov, (int(x), int(y)), int(k * (10 + 58 * e)), (255, 145, 50), max(2, int(4 * k)), cv2.LINE_AA)
                    u2 = (t - tc - 0.08) / 0.65
                    if 0 <= u2 < 1:
                        e2 = 1 - 2 ** (-10 * u2)
                        cv2.circle(ov, (int(x), int(y)), int(k * (8 + 40 * e2)), (255, 255, 255), max(1, int(2 * k)), cv2.LINE_AA)
                    a = 0.9 * (1 - u) ** 1.6
                    frame = cv2.addWeighted(ov, a, frame, 1 - a, 0)
            ff.stdin.write(frame.tobytes())
            n += 1
        i += 1
    ff.stdin.close()
    ff.wait()
    print(f"{n} frames -> {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--crop", required=True, help="y0:y1 rows of the source to keep (16:9 of the full width)")
    ap.add_argument("--size", required=True, help="WxH of the plate, e.g. 1486x836")
    ap.add_argument("--out-fps", type=float, default=30)
    ap.add_argument("--click", action="append", default=[], help="t:x:y in plate pixels (repeatable)")
    n = ap.parse_args(argv)
    y0, y1 = (int(v) for v in n.crop.split(":"))
    w, h = (int(v) for v in n.size.lower().split("x"))
    clicks = [tuple(float(v) for v in c.split(":")) for c in n.click]
    render(n.src, n.out, y0, y1, (w, h), n.out_fps, clicks)


if __name__ == "__main__":
    main()
