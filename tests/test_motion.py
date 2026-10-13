import struct,sys,tempfile,unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import motion,s2v


class MotionTests(unittest.TestCase):
 def fixture(self,root):
  p=Path(root);(p/"output").mkdir();(p/"work").mkdir()
  s2v.write(p/"project.json",{"schema":1,"title":"fixture","media":{"width":1920,"height":1080,"duration":12,"has_audio":True},"settings":{},"assets":{},"stages":{}})
  s2v.write(p/"captions.json",{"segments":[{"id":"c1","start":0,"end":3,"zh":"完全本地运行","en":"Runs fully locally."},{"id":"c2","start":3.2,"end":8,"zh":"点击这里开始生成","en":"Click here to generate."}]})
  s2v.write(p/"transcript.raw.json",{"segments":[{"id":"c1","start":0,"end":3,"text":"完全本地运行","words":[{"word":"完全","start":.1,"end":.5},{"word":"本地","start":.5,"end":.9},{"word":"运行","start":.9,"end":1.3}]},{"id":"c2","start":3.2,"end":8,"text":"点击这里开始生成"}]})
  return p

 def test_resolves_words_and_validates_all_effects(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[
    {"id":"h","type":"word_highlight","cue_id":"c1","text":"本地"},
    {"id":"k","type":"keyword","start":1.2,"end":2.2,"text":"完全本地","anchor":"top-left"},
    {"id":"u","type":"callout","start":3.5,"end":5,"target":{"x":.62,"y":.2,"w":.2,"h":.12},"label":"点这里"},
    {"id":"c","type":"chapter","start":6,"end":9.3,"title":"生成结果","subtitle":"Result"},
    {"id":"s","type":"sticker","start":10,"end":11.5,"source":"file:sticker.png","anchor":"top-right"}
   ]})
   result=motion.validate_plan(p)
   self.assertEqual(result["events"][0]["start"],.5)
   self.assertEqual({e["type"] for e in result["events"]},motion.VISUAL_TYPES)
   self.assertTrue((p/"output/motion-qa.json").is_file())

 def test_resegmented_cue_borrows_asr_words_by_time(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"captions.json",{"segments":[{"id":"c1m","start":0.4,"end":1.4,"zh":"本地运行","en":"Runs locally.","parent_ids":["c1"]},{"id":"c2","start":3.2,"end":8,"zh":"点击这里开始生成","en":"Click here to generate."}]})
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"h","type":"word_highlight","cue_id":"c1m","text":"运行"}]})
   result=motion.validate_plan(p)
   self.assertEqual((result["events"][0]["start"],result["events"][0]["end"]),(.9,1.3))

 def test_at_word_snaps_pop_to_speech_and_douyin_style(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"keyword_style":"douyin","events":[{"id":"k","type":"keyword","cue_id":"c1","at_word":"本地","text":"完全本地","emphasis":"本地","anchor":"top-left"}]})
   e=motion.validate_plan(p)["events"][0]
   self.assertAlmostEqual(e["start"],.5-.06*1.35,3);self.assertAlmostEqual(e["display_seconds"],1.3,2)
   self.assertEqual((e["style"],e["synced_word"]),("stroke","本地"))

 def test_sticker_rules_warn_on_density_and_source(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"a","type":"sticker","start":1,"end":3,"source":"noto:1f389"},{"id":"b","type":"sticker","start":4,"end":6,"source":"noto:1f602"}]})
   self.assertTrue(any("两个贴纸间隔不足" in w for w in motion.validate_plan(p)["warnings"]))
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"a","type":"sticker","start":1,"end":3,"source":"http://x"}]})
   with self.assertRaisesRegex(ValueError,"sticker.source"):motion.validate_plan(p)

 def test_default_flower_style_is_label_and_emphasis_checked(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"k","type":"keyword","start":1,"end":2.5,"text":"完全本地","anchor":"top-left"}]})
   self.assertEqual(motion.validate_plan(p)["events"][0]["style"],"label")
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"k","type":"keyword","start":1,"end":2.5,"text":"完全本地","emphasis":"云端","anchor":"top-left"}]})
   with self.assertRaisesRegex(ValueError,"emphasis"):motion.validate_plan(p)

 def test_chapter_duration_is_checked_after_speed(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"id":"c","type":"chapter","start":6,"end":7.4,"title":"生成结果","subtitle":"Result"}]})
   with self.assertRaisesRegex(ValueError,"1.35 倍速成片"):
    motion.validate_plan(p)

 def test_short_video_warns_when_chapter_cards_are_dense(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root)
   s2v.write(p/"motion-plan.json",{"schema":1,"events":[
    {"id":"c1","type":"chapter","start":0,"end":3,"title":"第一步"},
    {"id":"c2","type":"chapter","start":6,"end":9,"title":"第二步"}
   ]})
   result=motion.validate_plan(p)
   self.assertTrue(any("默认只保留 1 张" in warning for warning in result["warnings"]))
   self.assertAlmostEqual(result["events"][0]["display_seconds"],3/1.35,places=3)

 def test_invalid_callout_target_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   p=self.fixture(root);s2v.write(p/"motion-plan.json",{"schema":1,"events":[{"type":"callout","start":1,"end":2,"target":{"x":.9,"y":.2,"w":.2,"h":.1}}]})
   with self.assertRaises(ValueError):motion.validate_plan(p)

 def test_original_sfx_is_valid_sparse_pcm(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root);resolved={"events":[{"enabled":True,"start":1.0,"sfx":"pop"},{"enabled":True,"start":2.0,"sfx":"whoosh"}]}
   path,count=motion.render_sfx(p,resolved,0,1)
   self.assertEqual(count,2);self.assertEqual(path.read_bytes()[:4],b"RIFF")
   size=struct.unpack("<I",path.read_bytes()[40:44])[0]
   self.assertGreater(size,2*48000*2)

 def test_motion_settings_are_strict(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)
   for bad in ["yes",1,None]:
    s2v.write(p/"project.json",{"settings":{"motion_enabled":bad}})
    with self.assertRaises(ValueError):s2v.settings(p)
   s2v.write(p/"project.json",{"settings":{"sfx_db":-9}})
   self.assertEqual(s2v.settings(p)["sfx_db"],-9)


if __name__=="__main__":unittest.main()
