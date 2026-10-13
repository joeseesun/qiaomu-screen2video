#!/usr/bin/env python3
"""Optional, offline Jianying audio adapter; standard library + existing FFmpeg."""
import argparse
import array
import math
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import wave

import s2v

APP = Path('/Applications/VideoFusion-macOS.app/Contents')
PINNED = {
    'Frameworks/libsamicore.dylib': 'c0c215c22d7badf87d2f1523f3e1024b007f800ca3e587aaefb7767432759ca0',
    'Resources/audiosami/unet_denoise_44k_music_model_v1.0.model': 'a20cbd66d4ae8d483fe0f1759fa76803f4355d96aece3b65902b6cf34ff14c1c',
    'Resources/audiosami/time_align_freq_domain_v2.0.model': '0ef4a653b63dae44280509bc06c4b91f80e005738cd3fead9ba36530925ef56d',
}
SANDBOX = '(version 1)(allow default)(deny network*)'
LATENCY = 1024


def doctor(mode='all'):
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('剪映音频适配器需要 Apple Silicon macOS；可继续原声流程。')
    if not Path('/usr/bin/sandbox-exec').is_file() or not shutil.which('xcrun'):
        raise RuntimeError('需要 macOS sandbox-exec 和 Xcode Command Line Tools。')
    keys = ['Frameworks/libsamicore.dylib']
    if mode in ('all', 'denoise'):
        keys.append('Resources/audiosami/unet_denoise_44k_music_model_v1.0.model')
    if mode in ('all', 'align'):
        keys.append('Resources/audiosami/time_align_freq_domain_v2.0.model')
    for key in keys:
        path = APP / key
        if not path.is_file() or s2v.sha(path) != PINNED[key]:
            raise RuntimeError(f'剪映库/模型与已验证的 11.5.0 不符，需要重新验证 ABI：{path}')
    return {key: PINNED[key] for key in keys}


def executable(name):
    source = s2v.ROOT / 'scripts/native' / (name + '.c')
    key = s2v.sha(source)[:16]
    cache = Path.home() / '.cache/qiaomu-screen2video/native' / key
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if not target.exists():
        # Compile into a unique temporary path before making the cached binary visible.
        with tempfile.TemporaryDirectory(dir=cache) as td:
            temp = Path(td) / name
            s2v.run(['xcrun', 'clang', '-O2', '-arch', 'arm64', source, '-o', temp,
                     '-framework', 'Foundation', f'-Wl,-rpath,{APP}/Frameworks'])
            temp.replace(target)
    return target


def native(name, args, log):
    with Path(log).open('w') as f:
        result = subprocess.run(['/usr/bin/sandbox-exec', '-p', SANDBOX,
                                 str(executable(name)), *map(str, args)],
                                stdout=f, stderr=f, timeout=120)
    if result.returncode:
        raise RuntimeError(f'剪映本地处理失败（{result.returncode}），查看 {log}')


def pcm(path, rate):
    with wave.open(str(path), 'rb') as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype()) != (rate, 1, 2, 'NONE'):
            raise ValueError(f'需要 {rate} Hz 单声道 PCM16 WAV')
        data = array.array('h', w.readframes(w.getnframes()))
    if not data:
        raise ValueError('音频为空')
    return data


def wav(path, data, rate):
    with Path(path).open('xb') as f:
        with wave.open(f, 'wb') as w:
            w.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            w.writeframes(data.tobytes())


def denoise(source, output, work):
    pins = doctor('denoise')
    data = pcm(source, 44100)
    inp, out = work / 'denoise-in.f32', work / 'denoise-out.f32'
    inp.write_bytes(array.array('f', (x / 32768 for x in data)).tobytes())
    native('sami_denoise', [inp, out], work / 'denoise.log')
    samples = array.array('f', out.read_bytes())[LATENCY:LATENCY + len(data)]
    if len(samples) != len(data) or not all(math.isfinite(x) for x in samples):
        raise RuntimeError('降噪输出长度错误或存在无效采样')
    clipped = sum(abs(x) >= 1 for x in samples)
    if clipped:
        raise RuntimeError('降噪输出超出 PCM16 范围；保留原声并检查输入音量。')
    wav(output, array.array('h', (round(max(-1, min(32767 / 32768, x)) * 32768) for x in samples)), 44100)
    return {'identify': 308, 'strength': 'SDK default', 'latency_compensated_samples': LATENCY,
            'samples': len(samples), 'clipped_samples': clipped, 'pins': pins}


def correlation(reference, candidate, offset_ms, rate=16000):
    """Positive means candidate starts later: compare reference[t] with candidate[t+offset]."""
    lag = round(offset_ms * rate / 1000)
    a_start, b_start = max(0, -lag), max(0, lag)
    count = min(len(reference) - a_start, len(candidate) - b_start)
    if count < rate * 2:
        raise ValueError('对齐后共同音频不足两秒')
    # Downsample by averaging 8 samples, reducing phase sensitivity to 1 ms SDK rounding.
    a, b = [], []
    for i in range(0, count - 7, 8):
        a.append(sum(reference[a_start + i:a_start + i + 8]) / 8)
        b.append(sum(candidate[b_start + i:b_start + i + 8]) / 8)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    aa = sum((x - ma) ** 2 for x in a)
    bb = sum((x - mb) ** 2 for x in b)
    if min(aa / len(a), bb / len(b)) < 1:
        raise ValueError('静音/过低电平无法可靠对齐')
    return abs(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(aa * bb))


def refine_offset(reference, candidate, coarse_ms):
    """Refine the SDK's millisecond-quantized lag locally, never search a different event."""
    center = round(coarse_ms * 16)
    best = None
    for lag in range(center - 32, center + 33):
        sa, sb = max(0, -lag), max(0, lag)
        n = min(len(reference) - sa, len(candidate) - sb)
        if n < 32000:
            continue
        step = max(1, n // 12000)
        pairs = [(reference[sa + i], candidate[sb + i]) for i in range(0, n, step)]
        count = len(pairs)
        sx = sum(x for x, _ in pairs)
        sy = sum(y for _, y in pairs)
        xx = sum(x*x for x, _ in pairs) - sx*sx/count
        yy = sum(y*y for _, y in pairs) - sy*sy/count
        if min(xx / count, yy / count) < 1:
            continue
        xy = sum(x*y for x, y in pairs) - sx*sy/count
        score = abs(xy / math.sqrt(xx*yy))
        if best is None or score > best[0]:
            best = (score, lag)
    if best is None:
        raise ValueError('静音或有效重叠不足，无法可靠对齐')
    return best[1] / 16


def align(reference, candidate, work):
    pins = doctor('align')
    a, b = pcm(reference, 16000), pcm(candidate, 16000)
    # Bound resource use; this estimates one constant offset, not clock drift.
    n = min(max(len(a), len(b)), 60 * 16000)
    if n < 2 * 16000:
        raise ValueError('对齐检测至少需要两秒音频')
    paths = [work / 'align-ref.f32', work / 'align-voice.f32']
    for samples, path in zip([a, b], paths):
        values = array.array('f', (x / 32768 for x in samples[:n]))
        values.extend([0.0] * (n - len(values)))
        path.write_bytes(values.tobytes())
    result_path = work / 'align.json'
    native('sami_align', [*paths, result_path], work / 'align.log')
    result = s2v.read(result_path)
    coarse = result['offset_ms']
    if not math.isfinite(coarse):
        raise ValueError('无效对齐偏移')
    offset = refine_offset(a[:n], b[:n], coarse)
    score = correlation(a[:n], b[:n], offset)
    if score < .35:
        raise ValueError(f'对齐相关性不足（{score:.3f}）；两段必须包含同一次讲述，未替换原声。')
    return result | {'sdk_offset_ms': coarse, 'offset_ms': offset,
                     'refinement_range_ms': 2, 'absolute_correlation': score, 'window_seconds': n / 16000,
                     'sign': 'positive = candidate delayed; trim candidate start', 'pins': pins}


FFMPEG_DENOISE = 'highpass=f=70,afftdn=nr=12:nf=-42:tn=1,alimiter=limit=0.97:level=0'


def denoise_ffmpeg(source, output):
    """Portable fallback: FFmpeg's built-in spectral denoiser (no model download, any OS).
    Weaker than SAMI on non-stationary noise; tracks the noise floor (tn=1) so hum/fan hiss drop."""
    convert(source, output, 44100, FFMPEG_DENOISE)
    return {'engine': 'ffmpeg-afftdn', 'filters': FFMPEG_DENOISE}


def pick_denoise_engine(engine):
    if engine != 'auto':
        return engine
    try:
        doctor('denoise')
        return 'jianying'
    except Exception:
        return 'ffmpeg'


def convert(source, output, rate, filters=None):
    cmd = [s2v.ffmpeg(), '-v', 'error', '-n', '-i', source, '-map', '0:a:0', '-vn', '-ac', '1', '-ar', rate]
    if filters:
        cmd += ['-af', filters]
    s2v.run([*cmd, '-c:a', 'pcm_s16le', output])


def prepare(project, voice=None, use_denoise=False, denoise_engine='auto'):
    project = Path(project).expanduser().resolve()
    m = s2v.read(project / 'project.json')
    if not voice and not use_denoise:
        raise ValueError('指定 --denoise 和/或 --voice；恢复原声使用 --reset。')
    source = Path(m['source'])
    if s2v.sha(source) != m['source_sha256']:
        raise ValueError('源视频已修改，请创建新项目')
    voice = Path(voice).expanduser().resolve() if voice else None
    if voice and not voice.is_file():
        raise ValueError('独立录音不存在')
    denoise_engine = pick_denoise_engine(denoise_engine) if use_denoise else None
    if voice:
        doctor('align')
    if denoise_engine == 'jianying':
        doctor('denoise')
    s2v.status(project, 'audio', 'running', '本地处理讲述音频')
    # Unique run directory: failed requests cannot overwrite the previously selected audio.
    work = Path(tempfile.mkdtemp(prefix='audio-', dir=project / 'work'))
    try:
        details = {'network': 'native inference denied by macOS sandbox', 'source_sha256': m['source_sha256'],
                   'denoise': None, 'alignment': None, 'channels': 1, 'sample_rate': 44100}
        duration_samples = round(m['media']['duration'] * 44100)
        filters = f'aresample=44100,apad,atrim=end_sample={duration_samples},asetpts=PTS-STARTPTS'
        if voice:
            # Reference must be the original recorded voice, never the previous processing result.
            ref, candidate = work / 'reference.wav', work / 'candidate.wav'
            # Only decode the bounded search window for alignment.
            for inp, out in [(source, ref), (voice, candidate)]:
                convert(inp, out, 16000, 'atrim=duration=60,asetpts=PTS-STARTPTS')
            details['alignment'] = align(ref, candidate, work)
            offset_samples = round(details['alignment']['offset_ms'] * 44100 / 1000)
            shift = (f'atrim=start_sample={offset_samples},asetpts=PTS-STARTPTS' if offset_samples >= 0
                     else f'adelay={-offset_samples}S:all=1')
            filters = f'aresample=44100,{shift},apad,atrim=end_sample={duration_samples},asetpts=PTS-STARTPTS'
            details['external_voice_sha256'] = s2v.sha(voice)
        base = work / 'prepared.wav'
        convert(voice or source, base, 44100, filters)
        selected = base
        if use_denoise:
            selected = work / 'denoised.wav'
            details['denoise'] = (denoise(base, selected, work) | {'engine': 'jianying-sami'} if denoise_engine == 'jianying'
                                  else denoise_ffmpeg(base, selected))
        if len(pcm(selected, 44100)) != duration_samples:
            raise RuntimeError('处理后音频与视频时间轴不一致')
        asr_path = work / 'asr.wav'
        convert(selected, asr_path, 16000)
        s2v.write(work / 'processing.json', details)
        m['audio_processing'] = details | {
            'voice_path': str(selected.relative_to(project)), 'voice_sha256': s2v.sha(selected),
            'asr_path': str(asr_path.relative_to(project)), 'asr_sha256': s2v.sha(asr_path),
            'report_path': str((work / 'processing.json').relative_to(project))}
        # Re-read status fields written while the processing was running.
        m['stages'] = s2v.read(project / 'project.json').get('stages', {})
        s2v.write(project / 'project.json', m)
        invalidate(project)
        s2v.status(project, 'audio', 'done', '已启用' + ('独立录音对齐' if voice else '原声') + ('与降噪' if use_denoise else ''))
        return m['audio_processing']
    except Exception as e:
        s2v.status(project, 'audio', 'failed', str(e)[:500])
        raise


def invalidate(project):
    for phase in ('asr', 'captions', 'render'):
        s2v.status(project, phase, 'pending', '讲述音频已改变，需要重新识别/生成字幕和成片')


def reset(project):
    m = s2v.read(project / 'project.json')
    if m.pop('audio_processing', None) is not None:
        s2v.write(project / 'project.json', m)
        invalidate(project)
    s2v.status(project, 'audio', 'done', '恢复原音轨')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('project', type=Path, nargs='?')
    ap.add_argument('--doctor', action='store_true')
    ap.add_argument('--denoise', action='store_true')
    ap.add_argument('--denoise-engine', choices=['auto', 'jianying', 'ffmpeg'], default='auto',
                    help='auto: 剪映 SAMI 可用则用，否则 FFmpeg afftdn')
    ap.add_argument('--voice', type=Path)
    ap.add_argument('--reset', action='store_true')
    a = ap.parse_args()
    try:
        if a.doctor:
            print(doctor())
            return
        if a.project is None or (a.reset and (a.voice or a.denoise)):
            ap.error('提供项目目录；--reset 不能与处理选项一起使用')
        project = a.project.expanduser().resolve()
        if a.reset:
            reset(project)
        else:
            print(prepare(project, a.voice, a.denoise, a.denoise_engine))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
