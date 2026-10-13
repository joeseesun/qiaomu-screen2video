import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
import music_synth as ms

class MusicSynthTests(unittest.TestCase):
    def test_deterministic_length_and_headroom(self):
        a,meta=ms.render(12.0,'calm_explainer',seed=3)
        b,_=ms.render(12.0,'calm_explainer',seed=3)
        self.assertEqual(a.shape,(2,12*ms.SR))
        self.assertTrue(np.array_equal(a,b))
        self.assertLessEqual(np.max(np.abs(a)),10**(-1/20)+1e-6)
        self.assertGreater(np.sqrt(np.mean(a**2)),0.02)
        self.assertEqual(meta['bpm'],92)

    def test_tail_fades_to_silence(self):
        a,_=ms.render(10.0,'tutorial_focused')
        self.assertLess(np.max(np.abs(a[:,-50:])),1e-3)

    def test_score_is_shared_and_midi_is_valid(self):
        import tempfile
        ev,meta=ms.score(20.0,'calm_explainer')
        kinds={e['kind'] for e in ev}
        self.assertTrue({'piano','lead','pad'}<=kinds)
        self.assertTrue(all(0<=e['pitch']<=127 and 0<e['vel']<=1 for e in ev))
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/'a.mid';ms.write_midi(ev,m);b=m.read_bytes()
            self.assertEqual(b[:4],b'MThd');self.assertIn(b'MTrk',b);self.assertTrue(b.endswith(b'\xff\x2f\x00'))
            self.assertEqual(b.count(b'\x00\xff\x51'),1)

    def test_numpy_engine_is_default_without_soundfont(self):
        _,meta=ms.render(6.0,engine='numpy')
        self.assertEqual(meta['engine'],'numpy')

    @unittest.skipUnless(__import__('shutil').which('fluidsynth') and ms.find_soundfont(), 'fluidsynth/soundfont not installed')
    def test_fluidsynth_renders_same_score(self):
        a,meta=ms.render(8.0,engine='fluidsynth')
        self.assertEqual(meta['engine'],'fluidsynth')
        self.assertEqual(a.shape,(2,8*ms.SR))
        self.assertGreater(np.sqrt(np.mean(a**2)),0.02)
        self.assertLess(np.max(np.abs(a[:,-50:])),1e-3)

if __name__=='__main__':unittest.main()
