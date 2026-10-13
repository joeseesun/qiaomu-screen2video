import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import s2v,visual,asr

def ocr_frame(t,x,text='Edge TTS'):
    return {'t':t,'items':[{'text':text,'conf':1.0,'box':[x,0.4,0.05,0.02]},{'text':'很多企业正处在这样一个夹缝中，一方面','conf':1.0,'box':[0.1,0.1,0.6,0.03]}]}

class VisualTests(unittest.TestCase):
    def write(self,root,frames):
        p=Path(root);(p/'work').mkdir()
        s2v.write(p/'work/visual-analysis.json',{'schema':1,'ocr':frames,'vocabulary':visual.vocabulary(frames)})
        return p
    def test_stable_target_becomes_callout(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.write(d,[ocr_frame(10,0.40),ocr_frame(12,0.401)])
            r=visual.find(p,'edge tts',9,13)
            self.assertEqual(r['callout'],'ok');self.assertAlmostEqual(r['target']['x'],0.388,3)
    def test_moving_camera_rejects_fixed_callout(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.write(d,[ocr_frame(10,0.38),ocr_frame(12,0.55)])
            r=visual.find(p,'Edge TTS',9,13)
            self.assertEqual(r['callout'],'moving-use-keyword');self.assertIsNone(r['target'])
    def test_vocabulary_keeps_terms_not_body_text(self):
        v=visual.vocabulary([ocr_frame(0,.4,'Kokoro'),ocr_frame(2,.4,'Kokoro'),ocr_frame(4,.4,'Reader 3.2.1'),ocr_frame(6,.4,'Reader 4.0.1')])
        self.assertIn('Kokoro',v['terms']);self.assertIn('Reader',v['terms'])
        self.assertFalse(any('夹缝' in x for x in v['labels']))
    def test_screen_context_feeds_asr(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.write(d,[ocr_frame(0,.4,'MeloTTS'),ocr_frame(2,.4,'MeloTTS')])
            self.assertIn('MeloTTS',asr.screen_context(p))

class AsrSuspectTests(unittest.TestCase):
    def test_flags_single_char_lasting_seconds(self):
        data={'segments':[{'text':'正常','words':[{'word':'正常','start':0,'end':.4}]},
                          {'text':'质量稍微差一点','words':[{'word':'质','start':101.6,'end':101.8},{'word':'量','start':101.8,'end':104.9}]}]}
        self.assertEqual(asr.suspects(data),[1])

if __name__=='__main__':unittest.main()
