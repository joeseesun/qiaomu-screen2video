import importlib.util,json,math,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import s2v,asr

class CueTests(unittest.TestCase):
 def test_unicode_and_ids(self):
  c=s2v.normalize_cues([{'start':0,'end':1,'zh':'测试 Opus 5.5','en':'Test Opus 5.5.'}],2,True)
  self.assertEqual(c[0]['id'],'c0001')
 def test_nonfinite_and_overlap_rejected(self):
  for segments in [[{'start':float('nan'),'end':1,'text':'a'}],[{'start':0,'end':2,'text':'a'},{'start':1,'end':3,'text':'b'}],[{'start':0,'end':100,'text':'a'}]]:
   with self.assertRaises(ValueError):s2v.normalize_cues(segments,4)
 def test_translation_missing_rejected(self):
  with self.assertRaises(ValueError):s2v.normalize_cues([{'start':0,'end':1,'zh':'是','en':''}],2,True)
 def test_filler_empty_pair_allowed(self):
  c=s2v.normalize_cues([{'start':0,'end':1,'zh':'','en':''}],2,True);self.assertEqual(len(c),1)
 def test_ass_injection_neutralized(self):
  text=s2v.ass_text(r'{\pos(0,0)}bad\N')
  self.assertNotIn('{',text);self.assertNotIn('\\',text)
 def test_timing_rounding_carry(self):
  self.assertEqual(s2v.stamp(59.9999),'00:01:00,000');self.assertEqual(s2v.stamp(59.9999,True),'0:01:00.00')
 def test_html_escapes_script(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);s2v.write(p/'project.json',{'title':'</script><script>alert(1)</script>','media':{'duration':1},'settings':{},'assets':{},'source':'private/path','source_sha256':'secret'})
   s2v.report(p);out=(p/'review.html').read_text()
   self.assertNotIn('</script><script>alert',out);self.assertNotIn('private/path',out)
 def test_unknown_setting_no_mutation(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);m={'settings':{}};s2v.write(p/'project.json',m);s2v.write(p/'evil.json',{'command':'rm -rf /'})
   with self.assertRaises(ValueError):s2v.apply_decisions(p,p/'evil.json')
   self.assertEqual(s2v.read(p/'project.json'),m)
 def test_invalid_setting_rolls_back(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);m={'settings':{'intro_seconds':.7}};s2v.write(p/'project.json',m);s2v.write(p/'bad.json',{'intro_seconds':-7})
   with self.assertRaises(ValueError):s2v.apply_decisions(p,p/'bad.json')
   self.assertEqual(s2v.read(p/'project.json'),m)
 def test_optional_html_does_not_block_status(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);s2v.write(p/'project.json',{})
   with patch.object(s2v,'report',side_effect=OSError('simulated unavailable viewer')):s2v.status(p,'asr','done')
   self.assertEqual(s2v.read(p/'project.json')['stages']['asr']['state'],'done')
 def test_voice_loudness_setting_limits(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   for value in [True,0,float('nan'),-40]:
    s2v.write(p/'project.json',{'settings':{'voice_lufs':value}})
    with self.assertRaises(ValueError):s2v.settings(p)
   s2v.write(p/'project.json',{'settings':{'voice_lufs':-18}})
   self.assertEqual(s2v.settings(p)['voice_lufs'],-18)
 def test_doubao_business_error_not_success(self):
  class R:
   headers={'X-Api-Status-Code':'45000010'}
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return b'{}'
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.wav';p.write_bytes(b'fixture')
   with patch.dict('os.environ',{'DOUBAO_ASR_API_KEY':'test-not-real'}),patch('urllib.request.urlopen',return_value=R()) as u:
    with self.assertRaises(RuntimeError):asr.cloud_request(p)
    self.assertEqual(u.call_count,1)

if __name__=='__main__':unittest.main()
