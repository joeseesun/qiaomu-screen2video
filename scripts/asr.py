#!/usr/bin/env python3
"""ASR adapters. No helper/browser dependency, no credentials copied from Clipper."""
import argparse,base64,json,os,re,shutil,subprocess,sys,tempfile,time,urllib.error,urllib.request,uuid,wave
from pathlib import Path
from s2v import ffmpeg,read,write,run,status,import_transcript,selected_audio,sha

MODELS={'qwen':'Qwen/Qwen3-ASR-0.6B','mlx-whisper':'mlx-community/whisper-large-v3-turbo','faster-whisper':'Systran/faster-whisper-large-v3'}
MODULES={'qwen':'mlx_qwen3_asr','mlx-whisper':'mlx_whisper','faster-whisper':'faster_whisper','qwen-aligned':'qwen_asr'}

def runtime(engine,explicit=None):
 if explicit:return str(Path(explicit).expanduser())
 env=os.environ.get('SCREEN2VIDEO_ASR_PYTHON')
 if env:return env
 home=Path(os.environ.get('QIAOMU_TOOLS_HOME',Path.home()/'.local/share/qiaomu-clipper/tools'))
 folder={'qwen':'mlx-qwen3','mlx-whisper':'mlx','faster-whisper':'faster-whisper','qwen-aligned':'qwen-aligned'}[engine]
 candidates=[Path.home()/'.cache/qiaomu-screen2video'/('whisper' if engine=='mlx-whisper' else engine)/'bin/python',home/folder/'bin/python',Path.home()/'.local/share/uv/tools/mlx-whisper/bin/python',Path(sys.executable)]
 for p in candidates:
  if p.exists():
   r=subprocess.run([str(p),'-c',f'import importlib.util;exit(0 if importlib.util.find_spec("{MODULES[engine]}") else 1)'],capture_output=True,timeout=10)
   if r.returncode==0:return str(p)
 return None

def chunks(audio,maximum=12):
 with wave.open(str(audio),'rb') as f:total=f.getnframes()/f.getframerate()
 res=subprocess.run([ffmpeg(),'-hide_banner','-i',str(audio),'-af','silencedetect=noise=-35dB:d=0.2','-f','null','-'],capture_output=True,text=True)
 pauses=[float(x) for x in re.findall(r'silence_end: ([\d.]+)',res.stderr)]
 out=[];start=0
 while start<total-.01:
  target=min(total,start+maximum);choices=[x for x in pauses if start+maximum*.5<x<=target]
  end=max(choices) if choices and target<total else target;out.append((start,end));start=end
 return out

def cloud_request(path):
 key=os.environ.get('DOUBAO_ASR_API_KEY');app=os.environ.get('DOUBAO_ASR_APP_KEY');access=os.environ.get('DOUBAO_ASR_ACCESS_KEY')
 if not key and not(app and access):raise RuntimeError('缺少 DOUBAO_ASR_API_KEY，或 APP_KEY + ACCESS_KEY')
 headers={'Content-Type':'application/json','X-Api-Resource-Id':os.environ.get('DOUBAO_ASR_RESOURCE_ID','volc.bigasr.auc_turbo'),'X-Api-Request-Id':str(uuid.uuid4()),'X-Api-Sequence':'-1'}
 if key:headers['X-Api-Key']=key
 else:headers.update({'X-Api-App-Key':app,'X-Api-Access-Key':access})
 body={'user':{'uid':'qiaomu-screen2video'},'audio':{'data':base64.b64encode(path.read_bytes()).decode()},'request':{'model_name':'bigmodel','show_utterances':True}}
 endpoint=os.environ.get('DOUBAO_ASR_ENDPOINT','https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash')
 if not endpoint.startswith('https://'):raise ValueError('云端 ASR 端点必须使用 HTTPS')
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers=headers),timeout=180) as r:
    code=r.headers.get('X-Api-Status-Code','');data=json.loads(r.read())
    if code=='20000003':return []
    if code not in ('','20000000'):raise RuntimeError('豆包业务状态 '+code+'；检查额度/鉴权，未自动重试计费请求')
    utterances=data.get('result',{}).get('utterances')
    if not utterances:raise RuntimeError('豆包未返回句级时间戳，不按全文长度伪造时间')
    return [{'start':u['start_time']/1000,'end':u['end_time']/1000,'text':u['text']} for u in utterances]
  except urllib.error.HTTPError as e:
   if e.code in (429,500,502,503,504) and attempt<2:time.sleep(2**attempt);continue
   raise RuntimeError(f'豆包 HTTP {e.code}，凭据未写入日志') from None
 # Unknown network/timeout outcomes are not replayed automatically.

def worker(args):
 audio=Path(args.audio);model=args.model or MODELS.get(args.engine,'Qwen/Qwen3-ASR-0.6B');segments=[]
 language=None if args.language=='auto' else args.language
 if args.engine=='mlx-whisper':
  import mlx_whisper
  r=mlx_whisper.transcribe(str(audio),path_or_hf_repo=model,language=language,task='transcribe',word_timestamps=True,initial_prompt=args.context or None,condition_on_previous_text=False)
  segments=[{'start':s['start'],'end':s['end'],'text':s['text'],'words':s.get('words',[])} for s in r['segments']];timing='model-word'
 elif args.engine=='faster-whisper':
  import numpy as np
  from faster_whisper import WhisperModel
  # Decode known PCM directly, following Clipper's avoidance of PyAV version coupling.
  with wave.open(str(audio),'rb') as f:samples=np.frombuffer(f.readframes(f.getnframes()),np.int16).astype(np.float32)/32768
  seg,_=WhisperModel(model,device='cpu',compute_type='int8').transcribe(samples,language=language,word_timestamps=True,vad_filter=True,initial_prompt=args.context or None,condition_on_previous_text=False)
  segments=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in (s.words or [])]} for s in seg];timing='model-word'
 elif args.engine=='qwen':
  from mlx_qwen3_asr import Session
  session=Session(model=model)
  for i,(a,b) in enumerate(chunks(audio)):
   with tempfile.TemporaryDirectory(prefix='s2v-qwen-') as tmp:
    part=Path(tmp)/'audio.wav';run([ffmpeg(),'-v','error','-y','-ss',a,'-t',b-a,'-i',audio,'-c:a','pcm_s16le',part])
    r=session.transcribe(str(part),language={'zh':'Chinese','en':'English'}.get(language),context=args.context)
   text=(getattr(r,'text','') or '').strip()
   # No fabricated word timestamps. These pause-bounded chunks are explicitly coarse.
   if text:segments.append({'start':a,'end':b,'text':text})
   print(f'Qwen chunk {i+1}',file=sys.stderr,flush=True)
  timing='pause-chunk-estimated'
 elif args.engine=='qwen-aligned':
  import torch
  from qwen_asr import Qwen3ASRModel
  device='cuda:0' if torch.cuda.is_available() else 'cpu';dtype=torch.bfloat16 if device.startswith('cuda') else torch.float32
  q=Qwen3ASRModel.from_pretrained(model,dtype=dtype,device_map=device,forced_aligner='Qwen/Qwen3-ForcedAligner-0.6B',forced_aligner_kwargs={'dtype':dtype,'device_map':device})
  rr=q.transcribe(audio=str(audio),language={'zh':'Chinese','en':'English'}.get(language),return_time_stamps=True)
  for r in rr:
   words=[{'start':float(t.start_time),'end':float(t.end_time),'word':t.text} for t in r.time_stamps]
   group=[]
   for w in words:
    group.append(w)
    if w['end']-group[0]['start']>=3 or re.search('[。！？.!?]$',w['word']):
     segments.append({'start':group[0]['start'],'end':w['end'],'text':''.join(x['word'] for x in group),'words':group});group=[]
   if group:segments.append({'start':group[0]['start'],'end':group[-1]['end'],'text':''.join(x['word'] for x in group),'words':group})
  timing='forced-word'
 else:raise ValueError('未知引擎')
 write(args.output,{'engine':args.engine,'model':model,'timing':timing,'segments':segments})

def screen_context(project,limit=24):
 """On-screen product/model names from visual.py; ASR misspells these most (Kokoro, MeloTTS…)."""
 path=project/'work/visual-analysis.json'
 if not path.exists():return ''
 v=read(path).get('vocabulary') or {}
 if isinstance(v,list):v={'terms':v,'labels':[]}
 return '、'.join((v.get('terms') or [])[:limit]+(v.get('labels') or [])[:limit//2])

def _norm(t):return re.sub(r'[\s，。！？、,.!?「」"\']','',t or '').lower()

def suspects(data,max_char_seconds=1.2):
 """Segments whose word timing is implausible: a 1–2 char word lasting seconds usually means demo
 audio (TTS playback, music) was swallowed into the neighbouring speech."""
 out=[]
 for i,seg in enumerate(data.get('segments',[])):
  bad=[w for w in seg.get('words',[]) if len(_norm(w.get('word','')))<=2 and w.get('end',0)-w.get('start',0)>max_char_seconds]
  if bad:out.append(i)
 return out

def recheck(project,data,py,engine,audio,language,context,model=None,pad=1.5):
 """Re-run the same local engine on a short window around each suspect segment and keep the best
 matching contiguous run's timing. Text stays as first recognised; only start/end/words move."""
 import difflib
 report=[]
 for i in suspects(data):
  seg=data['segments'][i];ws=max(0.0,seg['start']-pad);we=seg['end']+pad
  with tempfile.TemporaryDirectory() as tmp:
   part=Path(tmp)/'w.wav';out=Path(tmp)/'r.json'
   run([ffmpeg(),'-v','error','-y','-ss',ws,'-t',we-ws,'-i',audio,'-ac','1','-ar','16000',part])
   cmd=[py,__file__,'--worker','--engine',engine,'--audio',str(part),'--output',str(out),'--language',language,'--context',context]
   if model:cmd+=['--model',model]
   if subprocess.run(cmd,capture_output=True).returncode or not out.exists():report.append({'segment':i,'status':'recheck-failed'});continue
   segs=read(out).get('segments',[])
  target=_norm(seg['text']);best=(0,None)
  for a in range(len(segs)):
   for b in range(a,len(segs)):
    r=difflib.SequenceMatcher(None,target,_norm(''.join(x['text'] for x in segs[a:b+1]))).ratio()
    if r>best[0]:best=(r,(a,b))
  if best[0]<0.6:report.append({'segment':i,'status':'no-match','ratio':round(best[0],2)});continue
  a,b=best[1];run_=segs[a:b+1]
  words=[dict(w,start=w['start']+ws,end=w['end']+ws) for x in run_ for w in x.get('words',[])]
  old=(seg['start'],seg['end']);seg['start']=round(run_[0]['start']+ws,3);seg['end']=round(run_[-1]['end']+ws,3)
  if words:seg['words']=words
  report.append({'segment':i,'status':'retimed','ratio':round(best[0],2),'from':old,'to':(seg['start'],seg['end'])})
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path,nargs='?');p.add_argument('--engine',choices=['auto','doubao',*MODULES],default='auto');p.add_argument('--python');p.add_argument('--model');p.add_argument('--language',default='zh');p.add_argument('--context',default='');p.add_argument('--no-screen-context',action='store_true');p.add_argument('--no-recheck',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--audio');p.add_argument('--output');a=p.parse_args()
 if a.worker:worker(a);return
 project=a.project.expanduser().resolve();m=read(project/'project.json');engine=a.engine
 if engine=='auto':
  engine='doubao' if (os.environ.get('DOUBAO_ASR_API_KEY') or (os.environ.get('DOUBAO_ASR_APP_KEY') and os.environ.get('DOUBAO_ASR_ACCESS_KEY'))) else next((e for e in ['mlx-whisper','faster-whisper','qwen'] if runtime(e,a.python)),None)
 if not engine:raise RuntimeError('没有可用 ASR。配置豆包，或安装独立 Whisper/Qwen 环境；不会自动上传到其他服务')
 audio=selected_audio(project,'asr')
 if not a.no_screen_context:
  extra=screen_context(project);a.context='、'.join(x for x in (a.context,extra) if x)
 dest=project/'work/asr-result.json';cachekey={'engine':engine,'model':a.model,'language':a.language,'context':a.context,'recheck':not a.no_recheck,'source':m['source_sha256'],'audio_sha256':sha(audio)}
 if dest.exists() and (project/'work/asr-cache.json').exists() and read(project/'work/asr-cache.json')==cachekey:
  import_transcript(project,dest);print('复用 ASR 缓存');return
 status(project,'asr','running',engine)
 try:
  if engine=='doubao':
   seg=[]
   for i,(start,end) in enumerate(chunks(audio,maximum=300)):
    part=project/f'work/asr-chunk-{i}.wav'
    try:
     run([ffmpeg(),'-v','error','-y','-ss',start,'-t',end-start,'-i',audio,'-c:a','pcm_s16le',part])
     seg.extend(dict(s,start=s['start']+start,end=s['end']+start) for s in cloud_request(part))
    finally:part.unlink(missing_ok=True)
   write(dest,{'engine':'doubao','timing':'service-utterance','segments':seg})
  else:
   py=runtime(engine,a.python)
   if not py:raise RuntimeError(engine+' 未安装；参见 references/asr.md')
   cmd=[py,__file__,'--worker','--engine',engine,'--audio',str(audio),'--output',str(dest),'--language',a.language,'--context',a.context]
   if a.model:cmd+=['--model',a.model]
   with open(project/'work/asr.log','w') as log:
    r=subprocess.run(cmd,stdout=log,stderr=log)
   if r.returncode:raise RuntimeError(engine+' 识别失败，查看 work/asr.log')
   if not a.no_recheck:
    data=read(dest);rep=recheck(project,data,py,engine,audio,a.language,a.context,a.model)
    if rep:write(dest,data);write(project/'work/asr-recheck.json',rep)
  import_transcript(project,dest);write(project/'work/asr-cache.json',cachekey)
 except Exception as e:
  status(project,'asr','failed',str(e));raise
if __name__=='__main__':main()
