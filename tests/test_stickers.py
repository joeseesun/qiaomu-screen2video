import subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image
import stickers

class StickerTests(unittest.TestCase):
    def test_local_png_becomes_alpha_clip_with_pop_in(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);Image.new('RGBA',(120,80),(240,90,60,255)).save(d/'s.png')
            path,credit=stickers.resolve('file:s.png',d)
            self.assertIsNone(credit)
            canvas=stickers.build_clip(path,d/'c.mov',1.0,30,100)
            out=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,pix_fmt,nb_frames','-of','csv=p=0',str(d/'c.mov')],capture_output=True,text=True).stdout.strip()
            self.assertEqual(out.split(',')[0],str(canvas));self.assertIn('rgba',out)
    def test_ease_starts_invisible_and_settles(self):
        self.assertEqual(stickers._ease_scale(0,2)[0],0.0)
        s,a,_=stickers._ease_scale(0.14,2);self.assertGreater(s,1.1)
        self.assertAlmostEqual(stickers._ease_scale(1.0,2)[0],1.0)
        self.assertLess(stickers._ease_scale(1.99,2)[1],0.1)
    def test_rejects_unknown_source(self):
        with self.assertRaises(ValueError):stickers.resolve('http://example.com/x.png','.')

if __name__=='__main__':unittest.main()
