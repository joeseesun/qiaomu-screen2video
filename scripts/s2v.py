#!/usr/bin/env python3
"""Screen recordings -> timed bilingual ASS -> FFmpeg. Python stdlib + Pillow/fonttools."""
import argparse, contextlib, hashlib, html, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parent.parent
DEFAULTS={'preset':'contrast','font_preset':'signature','placement':'overlay','intro_seconds':0.7,'outro_style':'terminal','outro_seconds':6.0,'fps':30,'speed':1.35,'music_db':-17,'music_fade_in':0.5,'music_fade_out':3.0,'ducking':True,'motion_enabled':True,'word_highlight':True,'sfx_enabled':True,'sfx_db':-6,'zh_size':56,'en_size':38,'voice_lufs':None,'final_lufs':-17,'final_lra':7,'true_peak':-1.5}

def read(p): return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2));os.replace(t,p)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(cmd,**kw):
 r=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,**kw)
 if r.returncode:raise RuntimeError(r.stderr[-5000:] or r.stdout[-1000:])
 return r.stdout
def ffmpeg():
 candidates=[os.environ.get('SCREEN2VIDEO_FFMPEG'),'/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg',shutil.which('ffmpeg')]
 for p in dict.fromkeys(candidates):
  if p and Path(p).is_file() and re.search(r'\bass\s+V->V',run([p,'-hide_banner','-filters'])):return p
 raise RuntimeError('FFmpeg 缺少 libass。macOS: brew install ffmpeg-full；或设置 SCREEN2VIDEO_FFMPEG。')
def probe(p):
 binary=os.environ.get('SCREEN2VIDEO_FFPROBE') or shutil.which('ffprobe')
 if not binary:raise RuntimeError('需要 ffprobe')
 return json.loads(run([binary,'-v','error','-show_streams','-show_format','-of','json',p]))
def media(p):
 d=probe(p);v=next((s for s in d['streams'] if s['codec_type']=='video'),None)
 if not v:raise ValueError('需要包含画面的录屏文件')
 rotation=next((s.get('rotation',0) for s in v.get('side_data_list',[]) if 'rotation' in s),0)
 w,h=v['width'],v['height']
 if abs(rotation)%180==90:w,h=h,w
 return {'width':w,'height':h,'duration':float(d['format']['duration']),'has_audio':any(s['codec_type']=='audio' for s in d['streams']),'fps':v['avg_frame_rate']}
def status(p,phase,state,detail=''):
 m=read(p/'project.json');m.setdefault('stages',{})[phase]={'state':state,'detail':detail,'updated':time.strftime('%Y-%m-%d %H:%M:%S')};write(p/'project.json',m)
 try:report(p)
 except Exception as e:print('HTML 生成失败（主流程继续）: '+str(e),file=sys.stderr)
def settings(p):
 m=read(p/'project.json');c=DEFAULTS|m.get('settings',{})
 if c['preset'] not in ('contrast','both-white','band') or c['placement'] not in ('overlay','band'):raise ValueError('未知字幕样式')
 if c['font_preset'] not in ('signature','editorial','accessible'):raise ValueError('未知字体组合')
 if c['outro_style'] not in ('none','pulse','terminal','editorial','community'):raise ValueError('未知片尾样式')
 for k,lo,hi in [('intro_seconds',0,3),('outro_seconds',0,20),('fps',12,60),('speed',.75,2),('music_db',-45,-8),('music_fade_in',0,3),('music_fade_out',0,5),('sfx_db',-18,0),('zh_size',24,80),('en_size',18,64)]:
  if isinstance(c[k],bool) or not isinstance(c[k],(int,float)) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('无效设置: '+k)
 if c['voice_lufs'] is not None and (isinstance(c['voice_lufs'],bool) or not isinstance(c['voice_lufs'],(int,float)) or not math.isfinite(c['voice_lufs']) or not -24<=c['voice_lufs']<=-14):raise ValueError('voice_lufs 必须为空或 -24 到 -14')
 for k,lo,hi in [('final_lufs',-20,-16),('final_lra',5,12),('true_peak',-3,-1)]:
  if isinstance(c[k],bool) or not isinstance(c[k],(int,float)) or not math.isfinite(c[k]) or not lo<=c[k]<=hi:raise ValueError('无效响度设置: '+k)
 for k in ['ducking','motion_enabled','word_highlight','sfx_enabled']:
  if not isinstance(c[k],bool):raise ValueError(k+' 必须为布尔值')
 if c['preset']=='band':c['placement']='band'
 return c

def selected_audio(p,kind='asr'):
 m=read(p/'project.json');a=m.get('audio_processing')
 if not a:return p/'work/audio.wav' if kind=='asr' else Path(m['source'])
 path=(p/a[kind+'_path']).resolve()
 if not path.is_relative_to((p/'work').resolve()):raise ValueError('处理音频必须位于项目 work 目录')
 if not path.is_file() or sha(path)!=a[kind+'_sha256']:raise ValueError('处理音频已改变或缺失，请重新执行 local_audio.py')
 return path

def audio_signature(p):
 return sha(selected_audio(p,'asr'))

def init(source,p):
 source=source.expanduser().resolve();p=p.expanduser().resolve();p.mkdir(parents=True,exist_ok=True)
 if (p/'project.json').exists():
  old=read(p/'project.json')
  if old['source_sha256']!=sha(source):raise ValueError('项目已经对应另一个源视频，请用新目录')
  if old.get('stages',{}).get('prepare',{}).get('state')=='done':
   report(p);return
 info=media(source)
 if not info['has_audio']:raise ValueError('录屏没有音轨；请提供字幕，或先提供有讲述音频的录屏')
 write(p/'project.json',{'schema':1,'title':source.stem,'source':str(source),'source_sha256':sha(source),'media':info,'settings':DEFAULTS,'assets':{},'stages':{}})
 for d in ['work','assets','output']: (p/d).mkdir(exist_ok=True)
 status(p,'prepare','running','提取识别用音频；成片仍使用原音轨')
 run([ffmpeg(),'-v','error','-y','-i',source,'-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',p/'work/audio.wav'])
 for i,t in enumerate([0.15,info['duration']*.35,info['duration']*.7]):
  run([ffmpeg(),'-v','error','-y','-ss',min(t,info['duration']/2 if info['duration']<1 else t),'-i',source,'-frames:v','1','-vf','scale=960:-2',p/f'assets/frame-{i}.jpg'])
 status(p,'prepare','done',f"{info['duration']:.1f} 秒 · {info['width']}×{info['height']}")
 print(p/'review.html')

def normalize_cues(data,total,bilingual=False):
 cues=data['segments'] if isinstance(data,dict) else data
 if not isinstance(cues,list) or not cues:raise ValueError('字幕为空')
 out=[];last=0;ids=set()
 for i,s in enumerate(cues):
  start=float(s['start']);end=float(s['end']);sid=str(s.get('id',f'c{i+1:04}'))
  if not all(map(math.isfinite,[start,end])) or start<0 or end<=start or end>total+.15:raise ValueError(f'{sid}: 时间超出范围')
  if start<last-.025:raise ValueError(f'{sid}: 时间重叠或乱序')
  if sid in ids:raise ValueError('重复字幕 ID: '+sid)
  ids.add(sid);last=end
  if bilingual:
   if not isinstance(s.get('zh'),str) or not isinstance(s.get('en'),str):raise ValueError(f'{sid}: 缺少 zh/en 文本')
   if bool(s['zh'].strip())!=bool(s['en'].strip()):raise ValueError(f'{sid}: 中英文必须配对，纯语气词可两项均为空')
  elif not isinstance(s.get('text'),str):raise ValueError('缺少 text')
  out.append(dict(s,id=sid,start=start,end=min(end,total)))
 return out

def import_transcript(p,path):
 m=read(p/'project.json');data=read(path);c=normalize_cues(data,m['media']['duration'])
 write(p/'transcript.raw.json',{'schema':1,'engine':data.get('engine','import') if isinstance(data,dict) else 'import','timing':data.get('timing','imported-segment') if isinstance(data,dict) else 'imported-segment','source_sha256':m['source_sha256'],'audio_sha256':audio_signature(p),'segments':c})
 write(p/'captions.draft.json',{'segments':[{'id':s['id'],'start':s['start'],'end':s['end'],'zh':s['text'],'en':''} for s in c]})
 status(p,'asr','done',f'{len(c)} 句，原始转写已保留')

def stamp(sec,ass=False):
 ticks=round(sec*(100 if ass else 1000));unit=100 if ass else 1000;h,rem=divmod(ticks,3600*unit);m,rem=divmod(rem,60*unit);s,ms=divmod(rem,unit)
 return f'{h}:{m:02}:{s:02}.{ms:02}' if ass else f'{h:02}:{m:02}:{s:02},{ms:03}'
def ass_text(s):return s.replace('\\','＼').replace('{','｛').replace('}','｝').replace('\r','').replace('\n',r'\N')
def wrap_text(text,font,max_width):
 # Preserve English words and product identifiers; CJK can wrap at glyph boundaries.
 tokens=re.findall(r'[A-Za-z0-9_./+@#:-]+(?:[’\x27][A-Za-z]+)?|\s+|.',text.replace('\n',' '))
 lines=[];line=''
 for token in tokens:
  if font.getlength((line+token).strip())<=max_width:line+=token
  else:
   if line.strip():lines.append(line.strip());line=''
   if font.getlength(token)>max_width:raise ValueError('不可拆分术语过长，请调整断句: '+token[:35])
   line=token.lstrip()
 if line.strip():lines.append(line.strip())
 return lines

def build_captions(p):
 from PIL import ImageFont
 from fontTools.ttLib import TTFont
 import fonts
 m=read(p/'project.json');c=settings(p);manifest=read(fonts.CACHE/'manifest.json');fm=manifest['presets'][c['font_preset']]
 cues=normalize_cues(read(p/'captions.json'),m['media']['duration'],True)
 raw=read(p/'transcript.raw.json');original={s['id']:s for s in raw['segments']}
 if (m.get('audio_processing') or raw.get('audio_sha256')) and raw.get('audio_sha256')!=audio_signature(p):raise ValueError('讲述音频已改变，请重新运行 ASR/导入对应转写并清理翻译字幕')
 # Clean/translate without changing ASR timing; intentional resegmentation requires explicit parent ids.
 changes=[]
 for s in cues:
  base=original.get(s['id'])
  if base and (abs(base['start']-s['start'])>.025 or abs(base['end']-s['end'])>.025):raise ValueError(s['id']+': 不要在清理文字时修改原时间；合并/拆分/重定时的字幕请换新 ID（如 '+s['id']+'m）并写 parent_ids')
  if not base:
   parents=s.get('parent_ids',[])
   if not isinstance(parents,list) or not parents or any(i not in original for i in parents):raise ValueError(s['id']+': 重分段需要有效 parent_ids')
   first=min(original[i]['start'] for i in parents);last=max(original[i]['end'] for i in parents)
   if s['start']<first-.025 or s['end']>last+.025:raise ValueError(s['id']+': 子段时间超出父段范围')
  if base and base['text']!=s['zh']:changes.append({'id':s['id'],'before':base['text'],'after':s['zh']})
 w=m['media']['width']//2*2;h=m['media']['height']//2*2
 scale=h/1080;zh_size=round(c['zh_size']*scale);en_size=round(c['en_size']*scale)
 band=round(h*.20)//2*2 if c['placement']=='band' else 0;out_h=h+band
 fz=ImageFont.truetype(fm['zh']['file'],zh_size);fe=ImageFont.truetype(fm['en']['file'],en_size)
 for lang in ['zh','en']:
  cmap=TTFont(fm[lang]['file']).getBestCmap();chars=set(''.join(x[lang] for x in cues));missing=[ch for ch in chars if not ch.isspace() and ord(ch) not in cmap]
  if missing:raise ValueError(lang+' 字体缺字: '+''.join(sorted(missing)))
 intro=round(c['intro_seconds']*c['fps'])/c['fps'] if m.get('assets',{}).get('cover') else 0
 speed=c['speed']
 styles=[];white='&H00FFFFFF';black='&H00121212'
 # ASS BackColour controls the shadow colour/alpha. Alpha is inverted:
 # 0x73 is about 55% opaque and 0x99 is about 40% opaque.
 for name,lang,size,fill,outline,stroke,back,shadow in [('ZH','zh',zh_size,white,black,2.35,'&H73000000',1.2),('EN','en',en_size,black if c['preset']=='contrast' else white,white if c['preset']=='contrast' else black,1.85,'&H99000000',0.8)]:
  bold=-1 if fm[lang]['weight']>=600 else 0
  styles.append(f"Style: {name},{fm[lang]['family']},{size},{fill},{fill},{outline},{back},{bold},0,0,0,100,100,0,0,1,{stroke*scale:.2f},{shadow*scale:.2f},2,0,0,0,1")
 header=f'[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {out_h}\nScaledBorderAndShadow: yes\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n'+'\n'.join(styles)+'\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
 events=[];srt={'zh':[],'en':[],'bilingual':[]};warnings=[];qa=[]
 for cue in cues:
  if not cue['zh'].strip():continue
  zl=wrap_text(cue['zh'],fz,w*.88);el=wrap_text(cue['en'],fe,w*.88)
  if len(zl)>2 or len(el)>2:raise ValueError(cue['id']+': 超过两行，请按语义缩短/重分段，禁止自动缩小字体')
  # Movie-style safe area: English sits near the lower 7%, Chinese above it.
  bottom=out_h-round(h*.075);zy=bottom-round(en_size*1.17*len(el)+h*.004)
  if band and zy-round(zh_size*1.3*len(zl))<h:raise ValueError(cue['id']+': 字幕带高度不足，请缩短句子')
  for name,lines,y in [('ZH',zl,zy),('EN',el,bottom)]:
   events.append(f"Dialogue: 0,{stamp(cue['start']/speed+intro,True)},{stamp(cue['end']/speed+intro,True)},{name},,0,0,0,,{{\\an2\\pos({w//2},{y})}}"+r'\N'.join(ass_text(x) for x in lines))
  a,b=stamp(cue['start']/speed+intro),stamp(cue['end']/speed+intro)
  for lang,text in [('zh','\n'.join(zl)),('en','\n'.join(el)),('bilingual','\n'.join(zl+el))]:srt[lang].append(f"{len(srt[lang])+1}\n{a} --> {b}\n{text}\n")
  dt=(cue['end']-cue['start'])/speed;zh_cps=len(re.findall(r'[\u3400-\u9fff]',cue['zh']))/dt;en_cps=len(cue['en'])/dt
  flags=[]
  if dt<.7:flags.append('显示时间偏短')
  if dt>7:flags.append('显示时间偏长')
  if zh_cps>9:flags.append('中文阅读速度偏快')
  if en_cps>20:flags.append('英文阅读速度偏快')
  if flags:warnings.append({'id':cue['id'],'warnings':flags})
  qa.append({'id':cue['id'],'zh_lines':len(zl),'en_lines':len(el)})
 if not events:raise ValueError('所有字幕均为空')
 (p/'output/subtitles.ass').write_text(header+'\n'.join(events)+'\n')
 for lang,blocks in srt.items():(p/f'output/{lang}.srt').write_text('\n'.join(blocks))
 write(p/'output/caption-qa.json',{'warnings':warnings,'layout':qa,'timing':raw.get('timing'),'text_changes':changes,'dimensions':[w,out_h],'intro_seconds':intro,'speed':speed})
 status(p,'captions','done',f'{len(cues)} 组双语字幕 · {len(warnings)} 条阅读提示')
 return w,h,band,intro,fm

def asset(p,kind,path,provider):
 if kind not in ['cover','music']:raise ValueError('未知资产')
 path=path.expanduser().resolve()
 if kind=='cover' and path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('封面需要 PNG/JPEG/WebP 静态图片')
 info=probe(path)
 wanted='video' if kind=='cover' else 'audio'
 if not any(s['codec_type']==wanted for s in info['streams']):raise ValueError('文件类型不匹配')
 if kind=='cover':
  from PIL import Image, ImageOps
  source_copy=p/'assets'/('cover-source'+path.suffix.lower())
  if path!=source_copy.resolve():shutil.copy2(path,source_copy)
  m=read(p/'project.json');target=(m['media']['width']//2*2,m['media']['height']//2*2)
  with Image.open(source_copy) as im:
   ImageOps.fit(im.convert('RGB'),target,method=Image.Resampling.LANCZOS,centering=(.5,.5)).save(p/'assets/cover.png',quality=95)
  dest=p/'assets/cover.png'
 else:
  dest=p/'assets'/(kind+path.suffix.lower())
  if path!=dest.resolve():shutil.copy2(path,dest)
 m=read(p/'project.json');m['assets'][kind]={'path':str(dest.relative_to(p)),'sha256':sha(dest),'provider':provider};write(p/'project.json',m)
 status(p,kind,'done','已取得本地文件：'+provider)

def fingerprint(p):
 m=read(p/'project.json');parts=[m['source_sha256'],settings(p),sha(Path(__file__))]
 parts.append(sha(selected_audio(p,'voice')))
 for name in ['captions.json','transcript.raw.json']:
  parts.append(sha(p/name) if (p/name).exists() else None)
 parts.append(sha(p/'motion-plan.json') if (p/'motion-plan.json').exists() else None)
 parts.append(sha(ROOT/'scripts/motion.py'));parts.append(sha(ROOT/'scripts/stickers.py'))
 for k in ['cover','music']:
  a=m.get('assets',{}).get(k);parts.append((k,sha(p/a['path'])) if a else (k,None))
 style=settings(p)['outro_style'];outros=m.get('assets',{}).get('outros',{}).get('styles',{})
 parts.append(('outro',style,sha(p/outros[style])) if style!='none' and style in outros else ('outro',None))
 import fonts
 parts.append(sha(fonts.CACHE/'manifest.json'))
 return hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest()

def measure_loudness(path,target_i=-17,target_tp=-1.5,target_lra=7):
 r=subprocess.run([ffmpeg(),'-hide_banner','-nostats','-i',str(path),'-vn','-af',f'loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json','-f','null','-'],capture_output=True,text=True)
 if r.returncode:raise RuntimeError('无法测量成片响度: '+r.stderr[-1000:])
 matches=re.findall(r'\{\s*"input_i".*?\}',r.stderr,re.S)
 if not matches:raise RuntimeError('FFmpeg 未返回响度数据')
 d=json.loads(matches[-1]);return {'integrated_lufs':float(d['input_i']),'true_peak_dbtp':float(d['input_tp']),'lra_lu':float(d['input_lra']),'threshold_lufs':float(d['input_thresh']),'target_offset':float(d['target_offset'])}

def render(p):
 m=read(p/'project.json');c=settings(p);source=Path(m['source'])
 if sha(source)!=m['source_sha256']:raise ValueError('源视频已修改，请创建新项目')
 available=m.get('assets',{}).get('outros',{});cached_duration=float(available.get('durations',{}).get(c['outro_style'],0))
 if c['outro_style']!='none' and c['outro_seconds']>0 and (c['outro_style'] not in available.get('styles',{}) or (c['outro_style']=='terminal' and cached_duration+0.01<c['outro_seconds'])):
  import outro_compose;outro_compose.make(p);m=read(p/'project.json')
 w,h,band,intro,fm=build_captions(p)
 import motion
 try:motion_info=motion.prepare(p,w,h,band,intro,fm)
 except Exception as e:
  status(p,'motion','failed',str(e)[:500]);raise
 if (p/'motion-plan.json').exists():status(p,'motion','done',f"{motion_info['events']} 个语义动效 · {len(motion_info['warnings'])} 条提示")
 else:status(p,'motion','pending','尚未生成 motion-plan.json；本次渲染基础字幕版')
 fp=fingerprint(p)
 if (p/'output/render.json').exists() and (p/'output/final.mp4').exists():
  old=read(p/'output/render.json')
  if old.get('fingerprint')==fp and old.get('output_sha256')==sha(p/'output/final.mp4'):
   status(p,'render','done','复用已验证成片，输入未变化');return
 status(p,'render','running','FFmpeg 正在烧录双语字幕并混音')
 out_h=h+band;main_dur=m['media']['duration']/c['speed']+intro;outro_seconds=c['outro_seconds'] if c['outro_style']!='none' else 0;dur=main_dur+outro_seconds;fps=c['fps'];cmd=[ffmpeg(),'-hide_banner','-y','-i',source];filters=[]
 # Use project-local aliases so ASS/fonts filter arguments never interpolate user paths.
 fontdir=p/'work/fonts';fontdir.mkdir(exist_ok=True)
 for lang in ['zh','en']:shutil.copy2(fm[lang]['file'],fontdir/(lang+'.ttf'))
 import motion as _motion
 if (p/'motion-plan.json').exists():shutil.copy2(_motion.flower_font(),fontdir/'flower.ttf')
 cover=m['assets'].get('cover') if intro>0 else None;music=m['assets'].get('music');idx=1
 if cover:cmd+=['-loop','1','-framerate',str(fps),'-t',str(intro),'-i',p/cover['path']];ci=idx;idx+=1
 if music:cmd+=['-stream_loop','-1','-i',p/music['path']];mi=idx
 if music:idx+=1
 voice_input='0:a'
 if m.get('audio_processing'):
  cmd+=['-i',selected_audio(p,'voice')];voice_input=f'{idx}:a';idx+=1
 sfx_path=motion_info.get('sfx')
 if sfx_path:cmd+=['-i',sfx_path];si=idx;idx+=1
 sticker_inputs=[]
 for clip in motion_info.get('stickers') or []:
  cmd+=['-i',clip['path']];sticker_inputs.append((idx,clip));idx+=1
 outro_path=None
 if outro_seconds:
  outro_path=p/m['assets']['outros']['styles'][c['outro_style']]
  if outro_path.suffix.lower() in ('.mp4','.mov','.mkv','.webm'):cmd+=['-i',outro_path]
  else:cmd+=['-loop','1','-framerate',str(fps),'-t',str(outro_seconds),'-i',outro_path]
  oi=idx;idx+=1
 filters.append(f'[0:v]scale={w}:{h},setsar=1,fps={fps},pad={w}:{out_h}:0:0:color=0x111827,format=yuv420p,setpts=(PTS-STARTPTS)/{c["speed"]}[main]')
 if cover:
  filters.append(f'[{ci}:v]scale={w}:{out_h}:force_original_aspect_ratio=increase,crop={w}:{out_h},setsar=1,fps={fps},format=yuv420p,setpts=PTS-STARTPTS[cover]')
  filters.append('[cover][main]concat=n=2:v=1:a=0[base]')
 else:filters.append('[main]null[base]')
 # Stickers sit above the picture but below subtitles and 花字, so text always stays readable.
 last='base'
 for n,(si_,clip) in enumerate(sticker_inputs):
  filters.append(f"[{si_}:v]format=rgba,setpts=PTS-STARTPTS+{clip['start']}/TB[stk{n}]")
  filters.append(f"[{last}][stk{n}]overlay=x={clip['x']}:y={clip['y']}:eof_action=pass:format=auto:enable='between(t,{clip['start']},{clip['end']})'[stkb{n}]");last=f'stkb{n}'
 filters.append(f"[{last}]ass=filename=output/subtitles.ass:fontsdir=work/fonts[subbed]")
 if motion_info.get('ass'):filters.append("[subbed]ass=filename=work/motion.ass:fontsdir=work/fonts[motioned]")
 else:filters.append('[subbed]null[motioned]')
 if outro_seconds:
  filters.append(f'[{oi}:v]scale={w}:{out_h}:force_original_aspect_ratio=increase,crop={w}:{out_h},setsar=1,fps={fps},format=yuv420p,trim=duration={outro_seconds},setpts=PTS-STARTPTS[outro]')
  filters.append('[motioned][outro]concat=n=2:v=1:a=0[vout]')
 else:filters.append('[motioned]null[vout]')
 voice_norm=f'loudnorm=I={c["voice_lufs"]}:TP=-1.5:LRA=11,' if c['voice_lufs'] is not None else ''
 filters.append(f'[{voice_input}]{voice_norm}aresample=48000,aformat=channel_layouts=stereo,atempo={c["speed"]},asetpts=PTS-STARTPTS,adelay={round(intro*1000)}:all=1,apad,atrim=duration={dur}[voice]')
 if music:
  filters.append(f'[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={dur},asetpts=PTS-STARTPTS,loudnorm=I=-18:TP=-2:LRA=7,volume={c["music_db"]}dB,afade=t=in:d={c["music_fade_in"]}:curve=hsin,afade=t=out:st={max(0,dur-c["music_fade_out"])}:d={c["music_fade_out"]}:curve=hsin[bed]')
  if c['ducking']:
   filters+=['[voice]asplit=2[voiceout][key]','[bed][key]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=400:makeup=1[ducked]','[voiceout][ducked]amix=inputs=2:duration=first:normalize=0[mixbase]']
  else:filters+=['[voice][bed]amix=inputs=2:duration=first:normalize=0[mixbase]']
 else:filters+=['[voice]anull[mixbase]']
 if sfx_path:
  filters.append(f'[{si}:a]aresample=48000,aformat=channel_layouts=stereo,volume={c["sfx_db"]}dB,apad,atrim=duration={dur}[sfx]')
  filters.append('[mixbase][sfx]amix=inputs=2:duration=first:normalize=0[premaster]')
 else:filters.append('[mixbase]anull[premaster]')
 filters.append('[premaster]aresample=48000[aout]')
 graph=';\n'.join(filters);(p/'work/render.ffgraph').write_text(graph)
 cmd+=['-filter_complex',graph,'-map','[vout]','-map','[aout]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(dur),'-movflags','+faststart','output/premaster.tmp.mp4']
 write(p/'work/render-command.json',[str(x) for x in cmd])
 with open(p/'work/render.log','w') as log:
  proc=subprocess.run([str(x) for x in cmd],cwd=p,stdout=log,stderr=log)
 if proc.returncode:raise RuntimeError('FFmpeg 失败，查看 work/render.log')
 logtext=(p/'work/render.log').read_text(errors='replace')
 if 'failed to find any fallback' in logtext:raise RuntimeError('ASS 字体缺字/回退失败，查看 work/render.log')
 for lang in ['zh','en']:
  if fm[lang].get('postscript') and not any('fontselect:' in line and fm[lang]['postscript'] in line for line in logtext.splitlines()):raise RuntimeError('未确认指定字体实际使用: '+fm[lang]['family'])
 premaster=p/'output/premaster.tmp.mp4';measured=measure_loudness(premaster,c['final_lufs'],c['true_peak'],c['final_lra']);tmp=p/'output/final.tmp.mp4'
 gain=c['final_lufs']-measured['integrated_lufs']
 # loudnorm silently falls back to dynamic mode when gain would break the true-peak ceiling; that lifts music-only
 # gaps and the outro toward speech level. Keep it linear: fixed gain + peak limiter on the few overshooting peaks.
 if measured['true_peak_dbtp']+gain>c['true_peak']-0.3:
  norm_mode='linear-gain+limiter';loudnorm=f'volume={gain:.3f}dB,alimiter=limit={10**((c["true_peak"]-0.3)/20):.6f}:attack=1:release=80:level=0:latency=1,aresample=48000'
 else:
  norm_mode='loudnorm-linear';loudnorm=f'loudnorm=I={c["final_lufs"]}:TP={c["true_peak"]}:LRA={c["final_lra"]}:measured_I={measured["integrated_lufs"]}:measured_LRA={measured["lra_lu"]}:measured_TP={measured["true_peak_dbtp"]}:measured_thresh={measured["threshold_lufs"]}:offset={measured["target_offset"]}:linear=true,aresample=48000'
 normcmd=[ffmpeg(),'-hide_banner','-y','-i',premaster,'-map','0:v:0','-map','0:a:0','-c:v','copy','-af',loudnorm,'-c:a','aac','-b:a','192k','-movflags','+faststart',tmp]
 write(p/'work/normalize-command.json',[str(x) for x in normcmd]);run(normcmd);premaster.unlink(missing_ok=True)
 first_pass=measure_loudness(tmp,c['final_lufs'],c['true_peak'],c['final_lra']);delta=c['final_lufs']-first_pass['integrated_lufs']
 if abs(delta)>.5:
  corrected=p/'output/final.corrected.tmp.mp4';limit=10**(c['true_peak']/20)
  correction=f'volume={delta:.3f}dB,alimiter=limit={limit:.6f}:level=0:latency=1,aresample=48000'
  fixcmd=[ffmpeg(),'-hide_banner','-y','-i',tmp,'-map','0:v:0','-map','0:a:0','-c:v','copy','-af',correction,'-c:a','aac','-b:a','192k','-movflags','+faststart',corrected]
  write(p/'work/loudness-correction-command.json',[str(x) for x in fixcmd]);run(fixcmd);os.replace(corrected,tmp)
 o=media(tmp)
 if abs(o['duration']-dur)>.2 or not o['has_audio'] or [o['width'],o['height']]!=[w,out_h]:raise RuntimeError('成片时长/尺寸/音轨验证未通过')
 # Decode entire export; distinguish an existing file from a healthy playable export.
 run([ffmpeg(),'-v','error','-i',tmp,'-f','null','-'])
 os.replace(tmp,p/'output/final.mp4')
 loudness=measure_loudness(p/'output/final.mp4',c['final_lufs'],c['true_peak'],c['final_lra'])
 if abs(loudness['integrated_lufs']-c['final_lufs'])>1 or loudness['true_peak_dbtp']>-1:raise RuntimeError(f'成片响度未达标: {loudness}')
 frames=[]
 for i,t in enumerate([min(.2,dur/2),intro+1,dur*.5,max(0,dur-1)]):
  name=f'output/check-{i}.jpg';run([ffmpeg(),'-v','error','-y','-ss',min(t,dur-.1),'-i',p/'output/final.mp4','-frames:v','1','-vf','scale=960:-2',p/name]);frames.append(name)
 write(p/'output/render.json',{'fingerprint':fp,'output_sha256':sha(p/'output/final.mp4'),'media':o,'intro_seconds':intro,'outro':{'style':c['outro_style'],'seconds':outro_seconds} if outro_seconds else None,'music':bool(music),'music_fades':{'in':c['music_fade_in'],'out':c['music_fade_out']} if music else None,'motion':{k:v for k,v in motion_info.items() if k not in ('ass','sfx','stickers')}|{'stickers':len(motion_info.get('stickers') or [])},'sfx':bool(sfx_path),'cover':bool(m['assets'].get('cover')),'audio_processing':m.get('audio_processing'),'loudness':loudness,'normalization':norm_mode,'premaster_loudness':measured,'loudness_target':{'integrated_lufs':c['final_lufs'],'true_peak_dbtp':c['true_peak'],'lra_lu':c['final_lra']},'decode':'passed','frames':frames,'visual_review':'pending','audio_review':'pending'})
 status(p,'render','done',f"{o['duration']:.1f} 秒 · {o['width']}×{o['height']} · 解码通过")
 print(p/'output/final.mp4')

def report(p):
 m=read(p/'project.json');payload={'project':m,'settings':settings(p),'captions':[],'brief':{},'render':{},'qa':{},'motion':{'events':[],'warnings':[]}}
 for f,k in [('captions.json','captions'),('brief.json','brief'),('output/render.json','render'),('output/caption-qa.json','qa'),('output/motion-qa.json','motion')]:
  if (p/f).exists():payload[k]=read(p/f)
 if isinstance(payload['captions'],dict):
  payload['review_notes']=payload['captions'].get('review_notes',[]);payload['captions']=payload['captions'].get('segments',[])
 # Self-contained data; no filesystem paths/secrets from raw ASR responses in the human page.
 payload['project'].pop('source',None);payload['project'].pop('source_sha256',None)
 if payload['render']:
  with contextlib.suppress(Exception):payload['render']['stale']=payload['render']['fingerprint']!=fingerprint(p)
 template=(ROOT/'assets/dashboard.html').read_text();data=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 (p/'review.html').write_text(template.replace('__PROJECT_DATA__',data))

def apply_decisions(p,path):
 d=read(path);m=read(p/'project.json');allowed=set(DEFAULTS)
 if any(k not in allowed for k in d):raise ValueError('仅接受样式/混音设置，不执行 HTML 中的任意命令')
 old=m.get('settings',{});m['settings']=old|d;write(p/'project.json',m)
 try:settings(p)
 except Exception:
  m['settings']=old;write(p/'project.json',m);raise
 status(p,'render','pending','设置已更新，需要重新渲染')

def main():
 ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
 x=sub.add_parser('init');x.add_argument('source',type=Path);x.add_argument('--project',required=True,type=Path)
 for name in ['captions','render','report','motion']:
  x=sub.add_parser(name);x.add_argument('project',type=Path)
 x=sub.add_parser('import-transcript');x.add_argument('project',type=Path);x.add_argument('file',type=Path)
 x=sub.add_parser('asset');x.add_argument('project',type=Path);x.add_argument('kind',choices=['cover','music']);x.add_argument('file',type=Path);x.add_argument('--provider',required=True)
 x=sub.add_parser('apply');x.add_argument('project',type=Path);x.add_argument('file',type=Path)
 args=ap.parse_args();p=args.project.expanduser().resolve()
 try:
  if args.command=='init':init(args.source,p)
  elif args.command=='import-transcript':import_transcript(p,args.file)
  elif args.command=='asset':asset(p,args.kind,args.file,args.provider)
  elif args.command=='apply':apply_decisions(p,args.file)
  elif args.command=='motion':
   import motion;result=motion.validate_plan(p,True);status(p,'motion','done',f"{sum(e['enabled'] for e in result['events'])} 个语义动效 · {len(result['warnings'])} 条提示")
  else:{'captions':build_captions,'render':render,'report':report}[args.command](p)
 except Exception as e:
  if (p/'project.json').exists():
   with contextlib.suppress(Exception):status(p,args.command,'failed',str(e)[:500])
  print(str(e),file=sys.stderr);return 1
 return 0
if __name__=='__main__':sys.exit(main())
