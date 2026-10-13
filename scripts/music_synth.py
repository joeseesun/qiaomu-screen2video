#!/usr/bin/env python3
"""Original code-composed instrumental bed for screen tutorials.

score() writes the arrangement once as note events; render_numpy() synthesises it from sine
partials and seeded noise (no samples, no network), render_fluidsynth() plays the same score
through a General MIDI SoundFont for real instrument timbres when one is installed.
Fallback after YuE2/Suno, and a fast option when the user asks for 代码配乐.
"""
import argparse
import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
NOTE = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6,
        'G': 7, 'Ab': 8, 'A': 9, 'Bb': 10, 'B': 11}
# I – V/3 – vi7 – IVmaj7, in scale degrees (semitones from tonic); calm, forward, unobtrusive.
PROGRESSION = [[0, 4, 7, 11], [-5, 2, 7, 11], [-3, 4, 7, 9], [-7, 4, 9, 12]]
BASS = [0, -8, -3, -7]
# Hand-written 8-bar lead over the 4-bar loop: (bar, beat, beats, semitone above tonic, F4 register).
# Phrase A asks (ends open on the 9th), phrase B answers higher and settles; mostly chord tones,
# stepwise, long notes on strong beats so it stays a bed under speech rather than a second voice.
MELODY = [
    (0, 0, 1.5, 12), (0, 1.5, .5, 9), (0, 2, 2, 7),
    (1, 0, 1.5, 7), (1, 1.5, .5, 4), (1, 2, 1, 2), (1, 3, 1, 4),
    (2, 0, 1.5, 9), (2, 1.5, .5, 7), (2, 2, 2, 4),
    (3, 0, 1, 5), (3, 1, 1, 4), (3, 2, 2, 7),
    (4, 0, 1, 12), (4, 1, 1, 14), (4, 2, 1.5, 16), (4, 3.5, .5, 14),
    (5, 0, 2, 14), (5, 2, 1, 11), (5, 3, 1, 7),
    (6, 0, 1.5, 9), (6, 1.5, .5, 12), (6, 2, 2, 9),
    (7, 0, 1, 7), (7, 1, 1, 5), (7, 2, 2, 4),
]
ENDING = [(0, 3, 12)]  # final bar: land on the tonic
PROFILES = {
    'tutorial_focused': dict(bpm=104, drums=1.0, shaker=1.0, motif=1.0),
    'calm_explainer': dict(bpm=92, drums=0.55, shaker=0.6, motif=0.8),
    'fast_demo': dict(bpm=116, drums=1.2, shaker=1.2, motif=1.0),
    'deep_build': dict(bpm=98, drums=0.8, shaker=0.4, motif=0.5),
}


def hz(semi, root):
    return 440.0 * 2 ** ((root + semi - 9) / 12)


def env(n, attack, decay):
    t = np.arange(n) / SR
    a = np.minimum(1.0, t / max(attack, 1e-4))
    return a * np.exp(-t / decay)


def piano(f, dur, vel):
    """Felt-piano-like tone: soft attack, inharmonic-ish partials, fast high decay."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, amp in [(1, 1.0), (2, 0.38), (3, 0.16), (4, 0.07), (5, 0.03)]:
        fk = f * k * (1 + 0.0004 * k * k)
        out += amp * np.sin(2 * np.pi * fk * t) * np.exp(-t * (1.6 + 1.3 * k))
    return vel * out * np.minimum(1.0, t / 0.008)


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            ff = f * 2 ** (det / 12)
            out += np.sin(2 * np.pi * ff * t) + 0.18 * np.sin(4 * np.pi * ff * t)
    shape = np.minimum(1.0, t / 0.9) * np.minimum(1.0, (dur - t) / 0.9)
    return out * np.clip(shape, 0, 1) / (len(freqs) * 3)


def kick(rng):
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    f = 46 + 70 * np.exp(-t * 32)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def shaker(rng):
    n = int(0.07 * SR)
    noise = rng.standard_normal(n + 8)
    noise = np.convolve(noise, np.ones(4) / 4, 'same')        # tame the top octave
    noise = np.diff(noise)[:n]                                 # remove lows → soft band-pass
    return noise * env(n, 0.006, 0.016) * 0.18


def rim(rng):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 820 * t) * np.exp(-t * 60)
    noise = np.diff(np.concatenate([[0], rng.standard_normal(n)])) * np.exp(-t * 45) * 0.3
    return (tone * 0.5 + noise) * 0.5


def add(buf, sig, start, pan=0.0, gain=1.0):
    i = int(start * SR)
    if i >= buf.shape[1]:
        return
    sig = sig[: buf.shape[1] - i] * gain
    buf[0, i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    buf[1, i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def room(buf, rng, mix=0.18):
    """Short seeded-noise impulse response reverb (FFT convolution)."""
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    out = np.empty_like(buf)
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t * 3.2)
        ir[: int(0.012 * SR)] = 0
        ir /= np.sqrt(np.sum(ir ** 2))
        size = 1 << int(np.ceil(np.log2(buf.shape[1] + n)))
        wet = np.fft.irfft(np.fft.rfft(buf[ch], size) * np.fft.rfft(ir, size), size)[: buf.shape[1]]
        out[ch] = buf[ch] + mix * wet
    return out


def score(seconds, profile='tutorial_focused', key='F', bpm=None, seed=7):
    """Arrangement as note events (MIDI pitches), shared by every renderer."""
    cfg = PROFILES[profile]
    bpm = bpm or cfg['bpm']
    beat = 60.0 / bpm
    bar = 4 * beat
    base = 60 + NOTE[key]  # semitone 0 == tonic in the F4 register
    rng = np.random.default_rng(seed)
    bars = int(np.ceil(seconds / bar)) + 1
    end_bar = int(seconds // bar)  # final bar rings out, no drums
    ev = []

    def note(kind, t, dur, pitch, vel, pan=0.0):
        ev.append({'kind': kind, 't': round(t, 4), 'dur': round(dur, 4), 'pitch': int(pitch),
                   'vel': round(float(min(1.0, vel)), 3), 'pan': pan})

    for b in range(bars):
        t0 = b * bar
        if t0 >= seconds:
            break
        chord = PROGRESSION[b % 4]
        section = 'intro' if b < 4 else 'outro' if b >= end_bar else 'break' if (b // 8) % 4 == 3 else 'main'
        last = b >= end_bar
        pad_dur = bar + 0.8 if not last else min(bar * 2, seconds - t0 + 2)
        for c in chord:
            note('pad', t0, pad_dur, base + c - 12, 0.5)
        # soft comping: low root + gentle broken chord, not a running arpeggio
        if last:
            for i, c in enumerate(chord[:3]):
                note('piano', t0 + i * 0.03, 4.5, base + c - 12, 0.45, -0.2 + 0.2 * i)
        else:
            for bt, idxs, vel in ((0, (0, 1, 2), 0.42), (1.5, (2,), 0.3), (2.5, (1, 3), 0.32), (3.5, (2,), 0.26)):
                for j, idx in enumerate(idxs):
                    note('piano', t0 + bt * beat + j * 0.012, 1.8, base + chord[idx] - 12,
                         vel * (0.9 + 0.1 * rng.random()), -0.3 + 0.2 * idx)
        if section != 'intro':
            for bt, v in ((0, 0.5), (2, 0.38)) if not last else ((0, 0.5),):
                note('bass', t0 + bt * beat, beat * 2.2, base + BASS[b % 4] - 24, v)
        if section == 'main':
            for bt in (0, 2):
                note('kick', t0 + bt * beat, 0.3, 36, 0.5 * cfg['drums'])
            for bt in (1, 3):
                note('rim', t0 + bt * beat + 0.01, 0.1, 37, 0.3 * cfg['drums'], 0.15)
            for x in range(16):
                note('shaker', t0 + x * beat / 4 + rng.normal(0, 0.003), 0.07, 70,
                     (0.5 if x % 4 == 2 else 0.28) * cfg['shaker'], 0.35)
        elif section == 'break':
            for x in range(8):
                note('shaker', t0 + x * beat / 2, 0.07, 70, 0.3 * cfg['shaker'], 0.35)
        # lead melody: plays 8 bars, rests 8 bars, so it breathes with the narration
        phrase = (b - 4) // 8
        if last:
            for bt, dur, semi in ENDING:
                note('lead', t0 + bt * beat, 4.0, base + semi, 0.5 * cfg['motif'], 0.1)
        elif section in ('main', 'intro') and (b < 4 or phrase % 2 == 0):
            local = (b if b < 4 else b - 4) % 8
            for mb, bt, dur, semi in MELODY:
                if mb == local:
                    note('lead', t0 + bt * beat, max(1.2, dur * beat + 0.6), base + semi,
                         0.5 * cfg['motif'] * (0.92 + 0.08 * rng.random()), 0.1)
    meta = dict(bpm=bpm, key=key, profile=profile, seed=seed, seconds=seconds)
    return ev, meta


def midi_hz(pitch):
    return 440.0 * 2 ** ((pitch - 69) / 12)


GAIN = {'pad': 0.22, 'piano': 0.26, 'bass': 0.45, 'lead': 0.24, 'kick': 0.4, 'rim': 0.4, 'shaker': 1.0}


def render_numpy(events, seconds, seed):
    rng = np.random.default_rng(seed)
    buf = np.zeros((2, int((seconds + 2.0) * SR)))
    k, shakers, r = kick(rng), [shaker(rng) for _ in range(6)], rim(rng)
    pads = {}
    for e in events:  # pads are rendered per chord so the detuned voices stay together
        if e['kind'] == 'pad':
            pads.setdefault((e['t'], e['dur']), []).append(midi_hz(e['pitch']))
    for (t, dur), freqs in pads.items():
        add(buf, pad(freqs, dur), t, 0.0, GAIN['pad'])
    for n, e in enumerate(events):
        kind = e['kind']
        if kind == 'pad':
            continue
        if kind in ('piano', 'lead'):
            sig = piano(midi_hz(e['pitch']), e['dur'], e['vel'])
        elif kind == 'bass':
            sig = piano(midi_hz(e['pitch']), e['dur'], 1.0) * 0.9 * e['vel'] / 0.5
        elif kind == 'kick':
            sig = k * e['vel']
        elif kind == 'rim':
            sig = r * e['vel']
        else:
            sig = shakers[n % len(shakers)] * e['vel']
        add(buf, sig, e['t'], e['pan'], GAIN[kind])
    return room(buf, rng)


# General MIDI mapping for SoundFont rendering: (channel, program)
GM = {'piano': (0, 0), 'lead': (1, 0), 'pad': (2, 89), 'bass': (3, 32)}
DRUMS = {'kick': 36, 'rim': 37, 'shaker': 70}


def write_midi(events, path):
    """Minimal type-0 SMF writer (960 ticks/quarter at 120 BPM → 1920 ticks/second)."""
    def vlq(n):
        out = [n & 0x7F]
        n >>= 7
        while n:
            out.insert(0, (n & 0x7F) | 0x80)
            n >>= 7
        return bytes(out)
    msgs = []
    for ch, prog in GM.values():
        msgs.append((0, 0, bytes([0xC0 | ch, prog])))
        msgs.append((0, 0, bytes([0xB0 | ch, 7, 100])))
    for e in events:
        if e['kind'] in DRUMS:
            ch, pitch = 9, DRUMS[e['kind']]
        else:
            ch, pitch = GM[e['kind']][0], e['pitch']
        on, off = round(e['t'] * 1920), round((e['t'] + e['dur']) * 1920)
        vel = max(1, min(127, round(e['vel'] * 127)))
        msgs.append((on, 1, bytes([0x90 | ch, pitch, vel])))
        msgs.append((off, 0, bytes([0x80 | ch, pitch, 0])))
    msgs.sort(key=lambda m: (m[0], m[1]))
    track, last = bytearray(b'\x00\xFF\x51\x03\x07\xA1\x20'), 0
    for tick, _, data in msgs:
        track += vlq(tick - last) + data
        last = tick
    track += b'\x00\xFF\x2F\x00'
    path.write_bytes(b'MThd' + (6).to_bytes(4, 'big') + (0).to_bytes(2, 'big') + (1).to_bytes(2, 'big')
                     + (960).to_bytes(2, 'big') + b'MTrk' + len(track).to_bytes(4, 'big') + bytes(track))


SOUNDFONT_DIRS = [Path.home() / '.cache/qiaomu-screen2video/soundfonts', Path('/opt/homebrew/share/soundfonts'),
                  Path('/usr/share/sounds/sf2'), Path('/usr/local/share/soundfonts')]


def find_soundfont(explicit=None):
    if explicit:
        return Path(explicit) if Path(explicit).is_file() else None
    for d in SOUNDFONT_DIRS:
        if d.is_dir():
            found = sorted(list(d.glob('*.sf2')) + list(d.glob('*.sf3')))
            if found:
                return found[0]
    return None


def render_fluidsynth(events, seconds, soundfont):
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which('fluidsynth')
    with tempfile.TemporaryDirectory() as tmp:
        mid, wav_path = Path(tmp) / 's.mid', Path(tmp) / 's.wav'
        write_midi(events, mid)
        subprocess.run([exe, '-ni', '-q', '-g', '0.6', '-r', str(SR), '-R', '1', '-C', '1',
                        '-F', str(wav_path), str(soundfont), str(mid)], check=True, capture_output=True)
        with wave.open(str(wav_path)) as w:
            raw = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 32768
            ch = w.getnchannels()
    buf = raw.reshape(-1, ch).T
    if ch == 1:
        buf = np.vstack([buf, buf])
    need = int((seconds + 2.0) * SR)
    return np.pad(buf, ((0, 0), (0, max(0, need - buf.shape[1]))))[:, :need]


def render(seconds, profile='tutorial_focused', key='F', bpm=None, seed=7, engine='auto', soundfont=None):
    import shutil
    events, meta = score(seconds, profile, key, bpm, seed)
    sf = find_soundfont(soundfont)
    use_fluid = engine == 'fluidsynth' or (engine == 'auto' and sf and shutil.which('fluidsynth'))
    if use_fluid:
        if not (sf and shutil.which('fluidsynth')):
            raise RuntimeError('fluidsynth 引擎需要 fluidsynth 可执行文件和 .sf2/.sf3 音色库')
        buf = render_fluidsynth(events, seconds, sf)
        meta.update(engine='fluidsynth', soundfont=sf.name)
    else:
        buf = render_numpy(events, seconds, seed)
        meta.update(engine='numpy')
    buf = buf[:, : int(seconds * SR)]
    # gentle tail fade so a looped/cut file never clicks
    fade = int(min(2.5, seconds / 4) * SR)
    buf[:, -fade:] *= np.linspace(1, 0, fade) ** 1.5
    # normalise on RMS with a soft clip so the drums cannot set the whole level
    buf *= 0.12 / max(1e-9, np.sqrt(np.mean(buf ** 2)))
    buf = np.tanh(buf * 1.1) / np.tanh(1.1)
    buf /= max(1.0, np.max(np.abs(buf)) / 10 ** (-1.0 / 20))
    meta['events'] = len(events)
    return buf, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    ap.add_argument('--seconds', type=float, required=True, help='最终成片总时长（含片头片尾）')
    ap.add_argument('--profile', choices=sorted(PROFILES), default='tutorial_focused')
    ap.add_argument('--key', choices=sorted(NOTE), default='F')
    ap.add_argument('--bpm', type=float)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--engine', choices=['auto', 'numpy', 'fluidsynth'], default='auto',
                    help='auto: 有 fluidsynth + 音色库则用真实乐器采样，否则纯代码合成')
    ap.add_argument('--soundfont', help='.sf2/.sf3 路径；默认查找 ~/.cache/qiaomu-screen2video/soundfonts 等')
    ap.add_argument('--midi', type=Path, help='另存同一编曲的 MIDI，便于在 DAW 里替换音色')
    a = ap.parse_args()
    audio, meta = render(a.seconds, a.profile, a.key, a.bpm, a.seed, a.engine, a.soundfont)
    if a.midi:
        write_midi(score(a.seconds, a.profile, a.key, a.bpm, a.seed)[0], a.midi)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio.T, -1, 1) * 32767).astype('<i2')
    with wave.open(str(a.output), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    meta.update(output=str(a.output), generator='qiaomu-screen2video/music_synth.py',
                samples=meta['engine'] == 'fluidsynth')
    a.output.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == '__main__':
    main()
