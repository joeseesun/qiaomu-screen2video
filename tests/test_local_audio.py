import array
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_audio
import s2v


class AudioBoundaries(unittest.TestCase):
    def test_shift_sign_and_silence(self):
        a = array.array('h', ((i * 137 % 3001) - 1500 for i in range(64000)))
        b = array.array('h', [0] * 16000) + a
        self.assertAlmostEqual(local_audio.correlation(a, b, 1000), 1)
        self.assertAlmostEqual(local_audio.correlation(b, a, -1000), 1)
        with self.assertRaises(ValueError):
            local_audio.correlation(array.array('h', [0] * 64000), b, 0)

    def test_pin_mismatch_rejected(self):
        with patch.object(local_audio.platform, 'system', return_value='Darwin'), \
             patch.object(local_audio.platform, 'machine', return_value='arm64'), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(local_audio.shutil, 'which', return_value='/usr/bin/xcrun'), \
             patch.object(s2v, 'sha', return_value='different'):
            with self.assertRaisesRegex(RuntimeError, '重新验证'):
                local_audio.doctor('denoise')

    def test_audio_tampering_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            audio = p / 'work/asr.wav'
            audio.parent.mkdir()
            audio.write_bytes(b'known audio')
            m = {'audio_processing': {'asr_path': 'work/asr.wav', 'asr_sha256': s2v.sha(audio)}}
            s2v.write(p / 'project.json', m)
            self.assertEqual(s2v.selected_audio(p), audio.resolve())
            audio.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, '改变或缺失'):
                s2v.selected_audio(p)
            m['audio_processing']['asr_path'] = '../outside.wav'
            s2v.write(p / 'project.json', m)
            with self.assertRaisesRegex(ValueError, 'work'):
                s2v.selected_audio(p)

    def test_processing_failure_preserves_selection(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            (p / 'work').mkdir()
            source = p / 'video.mp4'
            source.write_bytes(b'original')
            selection = {'voice_path': 'work/previous.wav'}
            s2v.write(p / 'project.json', {'source': str(source), 'source_sha256': s2v.sha(source),
                                         'media': {'duration': 4}, 'audio_processing': selection})
            with patch.object(local_audio, 'doctor'), \
                 patch.object(local_audio, 'convert', side_effect=RuntimeError('fixture decode failure')):
                with self.assertRaisesRegex(RuntimeError, 'decode'):
                    local_audio.prepare(p, use_denoise=True)
            self.assertEqual(s2v.read(p / 'project.json')['audio_processing'], selection)


if __name__ == '__main__':
    unittest.main()
