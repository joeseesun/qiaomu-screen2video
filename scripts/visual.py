#!/usr/bin/env python3
"""Look at the recording before editing: camera motion, stable windows, on-screen text.

analyze  → work/visual-analysis.json (samples, camera motion, stable windows, OCR, vocabulary)
find     → where a piece of on-screen text sits during a time window, and whether a fixed
           callout box would stay on it (auto-zoom / pan recordings drift).

Ideas adapted from Recordly / Reframed / OpenScreen (camera follows activity, so fixed
coordinates are unreliable) and OmniParser (locate UI targets from pixels, not guesses).
OCR uses Apple Vision through ocrmac on macOS; elsewhere OCR is skipped and reported.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2v  # noqa: E402

WIDTH = 1280


def sample_frames(project, fps):
    m = s2v.read(project / 'project.json')
    out = project / 'work/visual/frames'
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob('f*.jpg'):
        old.unlink()
    subprocess.run([s2v.ffmpeg(), '-v', 'error', '-y', '-i', m['source'], '-vf',
                    f'fps={fps},scale={WIDTH}:-2', '-q:v', '3', str(out / 'f%05d.jpg')], check=True)
    frames = sorted(out.glob('f*.jpg'))
    return [(round(i / fps, 3), f) for i, f in enumerate(frames)]


def camera_motion(a, b):
    """Similarity transform between consecutive frames: (scale, dx, dy) in frame-width units."""
    import cv2
    import numpy as np
    orb = cv2.ORB_create(1500)
    ka, da = orb.detectAndCompute(a, None)
    kb, db = orb.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 30 or len(kb) < 30:
        return None
    matches = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db), key=lambda x: x.distance)[:400]
    if len(matches) < 20:
        return None
    pa = np.float32([ka[x.queryIdx].pt for x in matches])
    pb = np.float32([kb[x.trainIdx].pt for x in matches])
    mat, inliers = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=3)
    if mat is None or inliers is None or inliers.sum() < 15:
        return None
    scale = float(np.hypot(mat[0, 0], mat[1, 0]))
    w = a.shape[1]
    return {'scale': round(scale, 4), 'dx': round(float(mat[0, 2]) / w, 4), 'dy': round(float(mat[1, 2]) / w, 4)}


def ocr(path):
    try:
        from ocrmac import ocrmac
    except ImportError:
        return None
    items = []
    for text, conf, (x, y, w, h) in ocrmac.OCR(str(path), language_preference=['zh-Hans', 'en-US'],
                                               recognition_level='accurate').recognize():
        # Vision boxes are bottom-left origin; convert to top-left like motion-plan targets.
        items.append({'text': text, 'conf': round(float(conf), 2),
                      'box': [round(x, 4), round(1 - y - h, 4), round(w, 4), round(h, 4)]})
    return items


def vocabulary(ocr_frames, limit=40):
    """Terms worth giving to ASR / caption cleanup.

    terms: latin product or model names (where ASR misspells most: Kokoro, MeloTTS…).
    labels: short CJK UI labels (≤6 chars, whole OCR line, no sentence punctuation);
    long body text is page content, not vocabulary.
    """
    terms, labels = {}, {}
    for frame in ocr_frames:
        seen_t, seen_l = set(), set()
        for item in frame['items']:
            if item['conf'] < 0.5:
                continue
            for tok in re.findall(r'[A-Za-z][A-Za-z0-9.+\-]*[A-Za-z0-9](?: ?(?:TTS|AI|API|GPT|[0-9.]+))?', item['text']):
                tok = re.sub(r' ?[0-9][0-9.]*$', '', tok).rstrip('.')  # Reader 3.2.1 → Reader
                if len(tok) >= 3 and not tok.isdigit():
                    seen_t.add(tok)
            text = item['text'].strip()
            if 2 <= len(text) <= 6 and re.fullmatch(r'[\u4e00-\u9fff]+(?: ?[A-Za-z0-9]+)?', text):
                seen_l.add(text)
        for tok in seen_t:
            terms[tok] = terms.get(tok, 0) + 1
        for tok in seen_l:
            labels[tok] = labels.get(tok, 0) + 1
    rank = lambda d: [k for k, n in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 2][:limit]
    return {'terms': rank(terms), 'labels': rank(labels)}


def analyze(project, fps=1.0, ocr_every=2.0, still=0.012):
    import cv2
    samples = sample_frames(project, fps)
    out, prev = [], None
    for t, f in samples:
        img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        motion = camera_motion(prev, img) if prev is not None else {'scale': 1.0, 'dx': 0.0, 'dy': 0.0}
        moving = motion is None or abs(motion['scale'] - 1) > still or abs(motion['dx']) > still or abs(motion['dy']) > still
        out.append({'t': t, 'frame': str(f.relative_to(project)), 'motion': motion, 'moving': bool(moving)})
        prev = img
    windows, start = [], None
    for i, s in enumerate(out):
        if not s['moving'] and start is None:
            start = out[i - 1]['t'] if i else s['t']
        if (s['moving'] or i == len(out) - 1) and start is not None:
            end = s['t'] if not s['moving'] else out[i - 1]['t']
            if end - start >= 1.0:
                windows.append({'start': start, 'end': end})
            start = None
    step = max(1, round(ocr_every * fps))
    ocr_frames, ocr_available = [], True
    for s in out[::step]:
        items = ocr(project / s['frame'])
        if items is None:
            ocr_available = False
            break
        ocr_frames.append({'t': s['t'], 'items': items})
    moving_ratio = sum(s['moving'] for s in out) / max(1, len(out))
    result = {'schema': 1, 'fps': fps, 'samples': out, 'stable_windows': windows,
              'moving_ratio': round(moving_ratio, 3), 'camera': 'dynamic' if moving_ratio > 0.25 else 'static',
              'ocr_available': ocr_available, 'ocr': ocr_frames, 'vocabulary': vocabulary(ocr_frames)}
    s2v.write(project / 'work/visual-analysis.json', result)
    return result


def find(project, text, start=None, end=None):
    data = s2v.read(project / 'work/visual-analysis.json')
    needle = text.lower().replace(' ', '')
    hits = []
    for frame in data['ocr']:
        if (start is not None and frame['t'] < start - 1) or (end is not None and frame['t'] > end + 1):
            continue
        for item in frame['items']:
            if needle in item['text'].lower().replace(' ', ''):
                hits.append({'t': frame['t'], 'text': item['text'], 'box': item['box'], 'conf': item['conf']})
                break
    if not hits:
        return {'text': text, 'hits': [], 'callout': 'not-found'}
    xs = [h['box'][0] + h['box'][2] / 2 for h in hits]
    ys = [h['box'][1] + h['box'][3] / 2 for h in hits]
    drift = max(max(xs) - min(xs), max(ys) - min(ys))
    width = max(h['box'][2] for h in hits)
    pad = 0.012
    box = [min(h['box'][0] for h in hits) - pad, min(h['box'][1] for h in hits) - pad]
    box += [max(h['box'][0] + h['box'][2] for h in hits) + pad - box[0],
            max(h['box'][1] + h['box'][3] for h in hits) + pad - box[1]]
    stable = drift <= max(0.02, width / 4)
    return {'text': text, 'hits': hits, 'drift': round(drift, 4),
            'target': {k: round(max(0.0, v), 4) for k, v in zip('xywh', box)} if stable else None,
            'callout': 'ok' if stable else 'moving-use-keyword'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('analyze', help='采样帧、镜头运动、稳定窗口、OCR 与屏幕词表')
    a.add_argument('project', type=Path)
    a.add_argument('--fps', type=float, default=1.0)
    a.add_argument('--ocr-every', type=float, default=2.0, help='每隔多少秒 OCR 一帧')
    f = sub.add_parser('find', help='查找屏幕文字位置并判断 callout 是否稳定')
    f.add_argument('project', type=Path)
    f.add_argument('--text', required=True)
    f.add_argument('--start', type=float)
    f.add_argument('--end', type=float)
    args = ap.parse_args()
    project = args.project.expanduser().resolve()
    if args.cmd == 'analyze':
        r = analyze(project, args.fps, args.ocr_every)
        print(json.dumps({k: r[k] for k in ('camera', 'moving_ratio', 'stable_windows', 'ocr_available')} |
                         {'vocabulary': r['vocabulary']}, ensure_ascii=False))
    else:
        print(json.dumps(find(project, args.text, args.start, args.end), ensure_ascii=False))


if __name__ == '__main__':
    main()
