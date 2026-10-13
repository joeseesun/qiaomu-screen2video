"""Real original SAMI + FFmpeg integration, no cloud calls. Generates its own speech fixture.

Run with the skill Python environment; requires macOS say/Tingting, verified Jianying,
Command Line Tools and cached fonts. Prints the retained fixture directory.
"""
import array
import json
import random
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import asr
import local_audio as audio
import s2v

root = Path(tempfile.mkdtemp(prefix='screen2video-local-audio-')).resolve()
checks = []
audio.doctor()
speech = root / 'speech.aiff'
s2v.run(['say', '-v', 'Tingting', '-r', '180', '-o', speech,
         '这是录屏音频处理测试。我们验证外置录音的时间对齐，清理底噪，再生成中英字幕。'])
clean = root / 'clean.wav'
audio.convert(speech, clean, 44100)
data = array.array('h', [0] * 44100) + audio.pcm(clean, 44100) + array.array('h', [0] * 44100)
clean.unlink()
audio.wav(clean, data, 44100)
rng = random.Random(197)
noisy = array.array('h', (max(-32768, min(32767, round(x + rng.gauss(0, 600)))) for x in data))
noisy_path = root / 'noisy.wav'
audio.wav(noisy_path, noisy, 44100)
duration = len(data) / 44100
source = root / '录屏 空格.mkv'
s2v.run([s2v.ffmpeg(), '-v', 'error', '-f', 'lavfi', '-i', f'testsrc2=size=640x360:rate=30:duration={duration}',
         '-i', noisy_path, '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'pcm_s16le', source])
project = root / 'job'
s2v.init(source, project)
raw = root / 'raw.json'
s2v.write(raw, {'engine': 'fixture-text', 'segments': [{'id': 'one', 'start': .1, 'end': 3.5, 'text': '录屏音频测试'}]})
s2v.import_transcript(project, raw)


def captions():
    s2v.write(project / 'captions.json', {'segments': [{'id': 'one', 'start': .1, 'end': 3.5,
                                                       'zh': '录屏音频测试', 'en': 'Screen recording audio test'}]})


captions()
before = s2v.fingerprint(project)
prepared = audio.prepare(project, use_denoise=True)
actual = audio.pcm(project / prepared['voice_path'], 44100)
assert len(actual) == round(s2v.read(project / 'project.json')['media']['duration'] * 44100)
noisy_corr = audio.correlation(data, noisy, 0, 44100)
cleaned_corr = audio.correlation(data, actual, 0, 44100)
assert cleaned_corr > noisy_corr, (cleaned_corr, noisy_corr)
assert s2v.fingerprint(project) != before
try:
    s2v.build_captions(project)
    raise AssertionError('old transcript must be rejected')
except ValueError as e:
    assert '音频已改变' in str(e)
checks.extend(['actual-denoise-improves-reference-correlation', 'length-and-latency-preserved', 'stale-transcript-rejected'])

# Exercise the ASR orchestrator against the actual selected WAV, using a mocked provider
# response only. This is routing/cache proof, NOT cloud recognition quality proof.
def provider(part):
    with __import__('wave').open(str(part)) as w:
        assert w.getframerate() == 16000
    assert s2v.sha(part) == s2v.sha(s2v.selected_audio(project))
    return [{'id': 'one', 'start': .1, 'end': 3.5, 'text': '录屏音频测试'}]

with patch.object(sys, 'argv', ['asr.py', str(project), '--engine', 'doubao']), \
     patch.object(asr, 'cloud_request', side_effect=provider) as call:
    asr.main()
    assert call.call_count == 1
with patch.object(sys, 'argv', ['asr.py', str(project), '--engine', 'doubao']), \
     patch.object(asr, 'cloud_request', side_effect=AssertionError('cache should be reused')):
    asr.main()
checks.append('asr-selected-audio-and-cache')

shift = round(1.375 * 44100)
delayed = root / 'delayed.wav'
advanced = root / 'advanced.wav'
audio.wav(delayed, array.array('h', [0] * shift) + data, 44100)
audio.wav(advanced, data[shift:], 44100)
offsets = []
for voice, expected in [(delayed, 1375), (advanced, -1375), (clean, 0)]:
    selected = audio.prepare(project, voice=voice)
    offset = selected['alignment']['offset_ms']
    assert abs(offset - expected) <= 2, (offset, expected)
    aligned = audio.pcm(project / selected['voice_path'], 44100)
    start = max(0, -round(offset * 44.1))
    assert audio.correlation(data[start:], aligned[start:], 0, 44100) > .98
    offsets.append({'expected_ms': expected, 'returned_ms': offset, 'score': selected['alignment']['absolute_correlation']})
checks.append('positive-negative-zero-offset-with-applied-shift')
silence = root / 'silence.wav'
audio.wav(silence, array.array('h', [0] * len(data)), 44100)
previous = s2v.read(project / 'project.json')['audio_processing']
try:
    audio.prepare(project, voice=silence)
    raise AssertionError('silence alignment must fail')
except ValueError:
    pass
assert s2v.read(project / 'project.json')['audio_processing'] == previous
checks.append('silence-rejection-preserves-previous-selection')

# Combined alignment + denoise, including renderer input indices with cover and music.
selected = audio.prepare(project, voice=delayed, use_denoise=True)
with patch.object(sys, 'argv', ['asr.py', str(project), '--engine', 'doubao']), \
     patch.object(asr, 'cloud_request', side_effect=provider) as call:
    asr.main()
    assert call.call_count == 1
assert s2v.read(project / 'transcript.raw.json')['audio_sha256'] == s2v.audio_signature(project)
captions()
music = root / 'test-music.wav'
s2v.run([s2v.ffmpeg(), '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=700:duration=2', '-c:a', 'pcm_s16le', music])
s2v.asset(project, 'music', music, 'synthetic-tone-test-only')
s2v.asset(project, 'cover', project / 'assets/frame-0.jpg', 'test-fixture')
s2v.render(project)
render = s2v.read(project / 'output/render.json')
assert render['decode'] == 'passed' and render['audio_processing']['voice_sha256'] == selected['voice_sha256']
command = s2v.read(project / 'work/render-command.json')
assert str(s2v.selected_audio(project, 'voice')) in command
assert '[3:a]' in (project / 'work/render.ffgraph').read_text()
mtime = (project / 'output/final.mp4').stat().st_mtime_ns
s2v.render(project)
assert (project / 'output/final.mp4').stat().st_mtime_ns == mtime
checks.extend(['combined-alignment-denoise', 'processed-voice-cover-music-render-decode', 'render-cache-reuse'])
decoded = project / 'work/final-voice-check.wav'
audio.convert(project / 'output/final.mp4', decoded, 44100,
              f'atrim=start={render["intro_seconds"]},asetpts=PTS-STARTPTS')
rendered_correlation = audio.correlation(audio.pcm(s2v.selected_audio(project, 'voice'), 44100),
                                       audio.pcm(decoded, 44100), 0, 44100)
assert rendered_correlation > .98
checks.append('decoded-export-matches-selected-voice-timeline')
audio.reset(project)
assert 'audio_processing' not in s2v.read(project / 'project.json')
assert s2v.selected_audio(project, 'voice') == source
assert '"stale": true' in (project / 'review.html').read_text()
checks.append('reset-and-export-stale')
result = {'result': 'passed', 'checks': checks, 'fixture_path': str(root), 'offsets': offsets,
          'noisy_correlation': noisy_corr, 'denoised_correlation': cleaned_corr,
          'rendered_voice_correlation': rendered_correlation,
          'decode': render['decode'], 'provider': 'mocked response; real selected WAV passed to orchestrator',
          'human_audio_review': 'pending'}
s2v.write(root / 'results.json', result)
print(json.dumps(result, ensure_ascii=False, indent=2))
