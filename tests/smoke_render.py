"""Real FFmpeg integration smoke. Requires fonts.py setup; leaves fixture for inspection."""
import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import s2v
root=Path(tempfile.mkdtemp(prefix='screen2video-smoke-'));src=root/'录屏 空格.mp4';music=root/'test-tone.wav'
s2v.run([s2v.ffmpeg(),'-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30:duration=7','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=7','-vf','format=yuv420p','-c:v','libx264','-c:a','aac','-shortest',src])
s2v.run([s2v.ffmpeg(),'-v','error','-f','lavfi','-i','sine=frequency=700:sample_rate=48000:duration=1','-c:a','pcm_s16le',music])
p=root/'job';s2v.init(src,p)
s2v.write(root/'raw.json',{'engine':'synthetic-test','timing':'word','segments':[{'id':'one','start':.1,'end':3.8,'text':'测试原声与配乐','words':[{'word':'测试','start':.1,'end':.7},{'word':'原声','start':.7,'end':1.3},{'word':'与','start':1.3,'end':1.5},{'word':'配乐','start':1.5,'end':2.1}]},{'id':'two','start':4,'end':6.6,'text':'点击这里生成结果'}]})
s2v.import_transcript(p,root/'raw.json');s2v.write(p/'captions.json',{'segments':[{'id':'one','start':.1,'end':3.8,'zh':'测试原声与配乐','en':'Voice and background music test'}]})
s2v.write(p/'captions.json',{'segments':[{'id':'one','start':.1,'end':3.8,'zh':'测试原声与配乐','en':'Voice and background music test'},{'id':'two','start':4,'end':6.6,'zh':'点击这里生成结果','en':'Click here to generate the result'}]})
s2v.write(p/'motion-plan.json',{'schema':1,'profile':'balanced','events':[{'id':'h','type':'word_highlight','cue_id':'one','text':'原声','reason':'逐词同步测试'},{'id':'k','type':'keyword','start':1.7,'end':2.7,'text':'重点效果','anchor':'top-left','reason':'花字测试'},{'id':'u','type':'callout','start':3.0,'end':4.0,'target':{'x':.62,'y':.16,'w':.22,'h':.18},'label':'点击这里','reason':'界面指引测试'},{'id':'c','type':'chapter','start':4.1,'end':7.0,'title':'生成结果','subtitle':'Result','reason':'章节卡测试'}]})
s2v.asset(p,'cover',p/'assets/frame-0.jpg','synthetic-test-image')
s2v.asset(p,'music',music,'synthetic-tone-test-only')
s2v.write(root/'settings.json',{'intro_seconds':0,'outro_style':'none','outro_seconds':0,'placement':'band','preset':'band'});s2v.apply_decisions(p,root/'settings.json');s2v.render(p)
result=s2v.read(p/'output/render.json');assert result['media']['height']==432;assert result['intro_seconds']==0;assert result['music'];assert result['decode']=='passed'
assert result['motion']['events']==4;assert result['sfx'];assert (p/'work/motion.ass').is_file();assert (p/'work/motion-sfx.wav').is_file()
original=(p/'output/final.mp4').stat().st_mtime_ns;s2v.render(p);assert (p/'output/final.mp4').stat().st_mtime_ns==original
s2v.write(root/'settings.json',{'music_db':-18,'ducking':False});s2v.apply_decisions(p,root/'settings.json');assert '"stale": true' in (p/'review.html').read_text();s2v.render(p);assert s2v.read(p/'output/render.json')['fingerprint']!=result['fingerprint']
print(json.dumps({'tests':['music-ducking-export','independent-subtitle-band','cover-intro-zero','word-highlight','keyword-flower-text','ui-callout','chapter-card','original-light-sfx','unicode-and-space-path','cache-reuse','settings-mark-stale','non-ducking-remix'],'result':'passed','fixture_path':str(root)},ensure_ascii=False))
