#!/usr/bin/env python3
"""Create Qiaomu end cards plus the reusable animated terminal outro."""
import argparse, json, math, os, shutil, subprocess, tempfile
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parent.parent
PROFILE=ROOT.parent/'qiaomu-profile'
AVATAR=ROOT/'assets/qiaomu-profile/qiaomu_avatar.jpeg'
if not AVATAR.is_file():AVATAR=PROFILE/'assets/qiaomu_highres_original.jpeg'
PUBLIC_QR=ROOT/'assets/qiaomu-profile/qiaomu_wechat_public_account_qr.jpg'
if not PUBLIC_QR.is_file():PUBLIC_QR=PROFILE/'assets/qiaomu_wechat_public_account_qr.jpg'
FONT_DIR=Path.home()/'.cache/qiaomu-screen2video/fonts'

@lru_cache(maxsize=64)
def font(name,size):
 path=FONT_DIR/name
 if not path.is_file():raise FileNotFoundError('先运行 scripts/fonts.py')
 return ImageFont.truetype(path,size)

@lru_cache(maxsize=24)
def avatar(size):
 with Image.open(AVATAR) as im:im=ImageOps.fit(im.convert('RGB'),(size,size),Image.Resampling.LANCZOS)
 mask=Image.new('L',(size,size));ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255)
 out=Image.new('RGBA',(size,size));out.paste(im,(0,0),mask);return out

def qr(size):
 with Image.open(PUBLIC_QR) as im:return ImageOps.fit(im.convert('RGB'),(size,size),Image.Resampling.NEAREST).convert('RGBA')

def text(d,xy,value,f,fill,stroke=0,stroke_fill='#000000'):
 """Draw subtle scalable separation without turning terminal text into a glow."""
 offset=max(1,round(f.size*.025))
 shadow_stroke=max(0,stroke-1)
 d.text((xy[0]+offset,xy[1]+offset),value,font=f,fill='#00000070',stroke_width=shadow_stroke,stroke_fill='#00000070')
 d.text(xy,value,font=f,fill=fill,stroke_width=stroke,stroke_fill=stroke_fill)
def ease(x):x=max(0,min(1,x));return 1-(1-x)**3
def phase(t,start,end):return ease((t-start)/(end-start))
def typed(value,p):return value[:max(0,min(len(value),round(len(value)*p)))]
def outro_opacity(t,duration,fade=.70,black_hold=.15):
 """Hold the completed card, then ease to a short clean black tail."""
 start=max(0,duration-fade-black_hold)
 return 1-max(0,min(1,(t-start)/fade)) if t>=start else 1

def x_icon(d,box,color='#D9FF3F',background='#0D1210'):
 """Official X glyph geometry, normalized from the 24-unit brand mark."""
 x0,y0,x1,y1=box;s=(x1-x0)/24
 outer=[(18.244,2.25),(21.552,2.25),(14.325,10.51),(22.827,21.75),(16.17,21.75),(10.956,14.933),(4.99,21.75),(1.68,21.75),(9.41,12.915),(1.254,2.25),(8.08,2.25),(12.793,8.481)]
 hole=[(17.083,19.77),(18.916,19.77),(7.084,4.126),(5.117,4.126)]
 d.polygon([(x0+a*s,y0+b*s) for a,b in outer],fill=color);d.polygon([(x0+a*s,y0+b*s) for a,b in hole],fill=background)
@lru_cache(maxsize=16)
def vector_mark(name,size):
 """Rasterize a pinned vector once, preserving its exact silhouette."""
 svg=ROOT/f'assets/icons/{name}.svg'
 with tempfile.TemporaryDirectory(prefix='qiaomu-wechat-') as tmp:
  subprocess.run(['qlmanage','-t','-s',str(size*4),'-o',tmp,str(svg)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  png=Path(tmp)/(svg.name+'.png')
  with Image.open(png) as source:
   # Quick Look renders an opaque black mark on white. Invert luminance to recover its mask.
   mask=ImageOps.invert(source.convert('L'));bounds=mask.getbbox();mask=mask.crop(bounds) if bounds else mask
   mask=ImageOps.contain(mask,(round(size*.76),round(size*.76)),Image.Resampling.LANCZOS)
   white=Image.new('RGBA',mask.size,'white');white.putalpha(mask);return white.copy()

def github_icon(im,d,box,color='#D9FF3F'):
 x0,y0,x1,y1=map(round,box);w=x1-x0
 d.ellipse((x0,y0,x1,y1),fill=color)
 mark=vector_mark('github',w);dark=Image.new('RGBA',mark.size,'#0D1210');dark.putalpha(mark.getchannel('A'))
 im.alpha_composite(dark,(x0+(w-mark.width)//2,y0+(w-mark.height)//2))

def wechat_icon(im,d,box,color='#07C160'):
 x0,y0,x1,y1=map(round,box);w=x1-x0
 d.rounded_rectangle((x0,y0,x1,y1),radius=max(2,round(w*.22)),fill=color)
 mark=vector_mark('wechat',w);im.alpha_composite(mark,(x0+(w-mark.width)//2,y0+(w-mark.height)//2))
def web_icon(d,box,color='#D9FF3F'):
 x0,y0,x1,y1=box;w=x1-x0;line=max(2,int(w*.075));d.ellipse(box,outline=color,width=line);d.ellipse((x0+w*.25,y0,x0+w*.75,y1),outline=color,width=line);d.line((x0,y0+w*.5,x1,y0+w*.5),fill=color,width=line)

def terminal_scene(w,h,t=9,duration=3.5):
 S=min(w,h);im=Image.new('RGBA',(w,h),'#050706');d=ImageDraw.Draw(im);m=int(S*.065);enter=phase(t,0,.35);wy=int((1-enter)*S*.035);alpha=round(255*enter)
 d.rounded_rectangle((m,m+wy,w-m,h-m+wy),radius=int(S*.025),fill=(13,18,16,alpha),outline=(49,68,59,alpha),width=max(2,int(S*.002)))
 for i,c in enumerate(['#FF6159','#FFBD2E','#28C941']):d.ellipse((m+int(S*(.035+i*.04)),m+wy+int(S*.035),m+int(S*(.055+i*.04)),m+wy+int(S*.055)),fill=c)
 if h/w>1.25:
  mono=font('AtkinsonHyperlegibleNext-SemiBold.ttf',int(S*.052));big=font('NotoSansSC-Bold.ttf',int(S*.082));small=font('AtkinsonHyperlegibleNext-SemiBold.ttf',int(S*.043));x=m+int(S*.065);y=m+wy+int(S*.14)
  text(d,(x,y),typed('$ whoami',phase(t,.28,.75)),mono,'#62FFD5');text(d,(x,y+int(S*.105)),typed('向阳乔木 / 乔帮主',phase(t,.72,1.35)),big,'#FFFFFF')
  avp=phase(t,.95,1.75);base=int(S*.43);av=int(base*max(.01,avp))
  if avp>0:
   a=avatar(base).resize((av,av),Image.Resampling.LANCZOS);ax=(w-av)//2;ay=m+wy+int(S*.34)+(base-av)//2;ring=int(S*.010);d.ellipse((ax-ring,ay-ring,ax+av+ring,ay+av+ring),outline='#62FFD5',width=max(3,ring));im.alpha_composite(a,(ax,ay))
  fy=m+wy+int(S*.84);text(d,(x,fy),typed('$ follow --platform all',phase(t,1.18,1.72)),mono,'#62FFD5');row=phase(t,1.58,2.12);rx=x+int((1-row)*S*.035);icon=int(S*.055)
  if row>0:
   iy=fy+int(S*.11);x_icon(d,(rx,iy,rx+icon,iy+icon));text(d,(rx+icon+int(S*.025),iy-int(S*.004)),'@vista8',mono,'#D9FF3F');gy=iy+int(S*.105);github_icon(im,d,(rx,gy,rx+icon,gy+icon));text(d,(rx+icon+int(S*.025),gy-int(S*.004)),'@joeseesun',mono,'#D9FF3F')
  web=phase(t,1.95,2.42)
  if web>0:
   wx=x+int((1-web)*S*.025);wechat_y=fy+int(S*.33);wechat_icon(im,d,(wx,wechat_y,wx+icon,wechat_y+icon));text(d,(wx+icon+int(S*.025),wechat_y-int(S*.004)),'向阳乔木推荐看',font('NotoSansSC-Bold.ttf',int(S*.045)),'#DDE7E3')
   sy=fy+int(S*.43);web_icon(d,(wx,sy,wx+icon,sy+icon));text(d,(wx+icon+int(S*.025),sy-int(S*.004)),'qiaomu.ai',small,'#DDE7E3')
  tag=typed('Build useful things with AI.',phase(t,2.28,3.0));cursor='  _' if int(t*3)%2==0 else '';text(d,(x,fy+int(S*.56)),tag+cursor,small,'#FFFFFF')
  fade=outro_opacity(t,duration)
  if fade<1:im.alpha_composite(Image.new('RGBA',(w,h),(0,0,0,round(255*(1-fade)))))
  return im.convert('RGB')
 mono=font('AtkinsonHyperlegibleNext-SemiBold.ttf',int(S*.036));big=font('NotoSansSC-Bold.ttf',int(S*.066));small=font('AtkinsonHyperlegibleNext-SemiBold.ttf',int(S*.030));x=m+int(S*.06);y=m+wy+int(S*.125)
 text(d,(x,y),typed('$ whoami',phase(t,.28,.75)),mono,'#62FFD5')
 text(d,(x,y+int(S*.085)),typed('向阳乔木 / 乔帮主',phase(t,.72,1.35)),big,'#FFFFFF')
 text(d,(x,y+int(S*.205)),typed('$ follow --platform all',phase(t,1.18,1.72)),mono,'#62FFD5')
 row=phase(t,1.58,2.12);rx=x+int((1-row)*S*.035);iy=y+int(S*.30);icon=int(S*.035)
 if row>0:
  x_icon(d,(rx,iy,rx+icon,iy+icon));text(d,(rx+icon+int(S*.015),iy-int(S*.006)),'@vista8',mono,'#D9FF3F')
  gx=rx+int(S*.30);github_icon(im,d,(gx,iy,gx+icon,iy+icon));text(d,(gx+icon+int(S*.015),iy-int(S*.006)),'@joeseesun',mono,'#D9FF3F')
 web=phase(t,1.95,2.42)
 if web>0:
  wx=x+int((1-web)*S*.025);wechat_y=y+int(S*.39);wechat_icon(im,d,(wx,wechat_y,wx+icon,wechat_y+icon));text(d,(wx+icon+int(S*.015),wechat_y-int(S*.004)),'向阳乔木推荐看',font('NotoSansSC-Bold.ttf',int(S*.030)),'#DDE7E3')
  sx=wx+int(S*.39);web_icon(d,(sx,wechat_y,sx+icon,wechat_y+icon));text(d,(sx+icon+int(S*.015),wechat_y-int(S*.004)),'qiaomu.ai',small,'#DDE7E3')
 tag=typed('Build useful things with AI.',phase(t,2.28,3.0));cursor='  _' if int(t*3)%2==0 else ''
 text(d,(x,y+int(S*.51)),tag+cursor,small,'#FFFFFF')
 avp=phase(t,.95,1.75);av=int(S*.255*max(.01,avp));base=int(S*.255)
 if avp>0:
  a=avatar(base).resize((av,av),Image.Resampling.LANCZOS);ax=w-m-int(S*.065)-av//2-base//2;ay=m+wy+int(S*.19)+(base-av)//2
  ring=int(S*.008);d.ellipse((ax-ring,ay-ring,ax+av+ring,ay+av+ring),outline='#62FFD5',width=max(3,ring));im.alpha_composite(a,(ax,ay))
 # A short fade to black makes automatic concatenation end cleanly.
 fade=outro_opacity(t,duration)
 if fade<1:
  veil=Image.new('RGBA',(w,h),(0,0,0,round(255*(1-fade))));im.alpha_composite(veil)
 return im.convert('RGB')

def card(style,w,h):
 if style=='terminal':return terminal_scene(w,h,3.2,9)
 S=min(w,h);pad=int(S*.075);title=font('NotoSansSC-Bold.ttf',int(S*.085));body=font('NotoSansSC-Bold.ttf',int(S*.034));en=font('AtkinsonHyperlegibleNext-SemiBold.ttf',int(S*.028))
 if style=='pulse':
  im=Image.new('RGB',(w,h),'#07100F').convert('RGBA');glow=Image.new('RGBA',(w,h));g=ImageDraw.Draw(glow);g.ellipse((w*.48,-h*.35,w*1.18,h*.75),fill='#58FFD640');g.ellipse((-w*.25,h*.55,w*.45,h*1.35),fill='#D9FF3F36');im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(S*.12))));d=ImageDraw.Draw(im);av=int(S*.27);im.alpha_composite(avatar(av),(pad,int(h*.5-av/2)));x=pad+av+int(S*.06);text(d,(x,int(h*.31)),'向阳乔木',title,'#FFFFFF',max(2,int(S*.0025)),'#000000');text(d,(x,int(h*.48)),'把 AI 前沿变成可用工作流',body,'#D9FF3F');text(d,(x,int(h*.60)),'X  @vista8    ·    GitHub  @joeseesun',en,'#DDE7E3');text(d,(x,int(h*.69)),'qiaomu.ai',en,'#8FA59E');text(d,(x,int(h*.81)),'关注我，继续一起折腾 AI  →',body,'#FFFFFF')
 elif style=='editorial':
  im=Image.new('RGB',(w,h),'#F2EEE5').convert('RGBA');d=ImageDraw.Draw(im);d.rectangle((0,0,int(w*.037),h),fill='#D9FF3F');d.line((pad,int(h*.19),w-pad,int(h*.19)),fill='#171917',width=max(2,int(S*.002)));text(d,(pad,int(h*.24)),'向阳乔木',title,'#111311');text(d,(pad,int(h*.40)),'实践 AI，而不只是谈论 AI。',body,'#111311');text(d,(pad,int(h*.55)),'AI PRODUCT  /  AI CODING  /  GEO',en,'#4C514D');text(d,(pad,int(h*.69)),'@vista8   ·   @joeseesun   ·   qiaomu.ai',en,'#111311');text(d,(pad,int(h*.82)),'关注 · 收藏 · 继续看下一个实践',body,'#111311');av=int(S*.30);im.alpha_composite(avatar(av),(w-pad-av,int(h*.5-av/2)))
 elif style=='community':
  im=Image.new('RGB',(w,h),'#151126').convert('RGBA');glow=Image.new('RGBA',(w,h));g=ImageDraw.Draw(glow);g.ellipse((-w*.2,-h*.4,w*.55,h*.8),fill='#795CFF55');im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(int(S*.1))));d=ImageDraw.Draw(im);x=pad;text(d,(x,int(h*.24)),'继续一起学习 AI',title,'#FFFFFF');text(d,(x,int(h*.42)),'公众号｜向阳乔木推荐看',body,'#D9FF3F');text(d,(x,int(h*.54)),'X @vista8  ·  GitHub @joeseesun',en,'#E6E1FF');text(d,(x,int(h*.66)),'qiaomu.ai',en,'#AAA0D7');q=int(S*.33);qx=w-pad-q;qy=int(h*.5-q/2);d.rounded_rectangle((qx-int(S*.018),qy-int(S*.018),qx+q+int(S*.018),qy+q+int(S*.018)),radius=int(S*.02),fill='white');im.alpha_composite(qr(q),(qx,qy))
 return im.convert('RGB')

def render_terminal(path,w,h,duration,fps=30):
 ffmpeg=os.environ.get('SCREEN2VIDEO_FFMPEG') or ('/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg' if Path('/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg').is_file() else shutil.which('ffmpeg'))
 cmd=[ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(path)]
 proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 try:
  frames=math.ceil(duration*fps)
  for i in range(frames):proc.stdin.write(terminal_scene(w,h,i/fps,duration).tobytes())
  proc.stdin.close();err=proc.stderr.read();rc=proc.wait()
  if rc:raise RuntimeError(err.decode(errors='replace')[-3000:])
 except Exception:
  proc.kill();raise

def make(project,variants=False):
 data=json.loads((project/'project.json').read_text());w=data['media']['width']//2*2;h=data['media']['height']//2*2;out=project/'assets';out.mkdir(exist_ok=True);files={};durations={}
 duration=max(3.5,float(data.get('settings',{}).get('outro_seconds',6.0)))
 for style in ['pulse','terminal','editorial','community']:
  preview=out/f'outro-{style}.png';card(style,w,h).save(preview,quality=95)
  if style=='terminal':
   video=out/'outro-terminal.mp4';render_terminal(video,w,h,duration);files[style]=str(video.relative_to(project));durations[style]=duration
  else:files[style]=str(preview.relative_to(project))
 distribution=dict(data.get('assets',{}).get('outros',{}).get('distribution_variants',{}))
 if variants:
  for name,vw,vh in [('16x9',1920,1080),('9x16',1080,1920)]:
   vp=out/f'outro-terminal-{name}.mp4';render_terminal(vp,vw,vh,duration);distribution[name]=str(vp.relative_to(project))
 data.setdefault('assets',{})['outros']={'provider':'qiaomu-profile + deterministic animated Pillow/FFmpeg','styles':files,'durations':durations,'distribution_variants':distribution};(project/'project.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
 tiles=''.join(f'<figure><img src="assets/outro-{s}.png"><figcaption>{s}</figcaption></figure>' for s in files)
 (project/'outro-gallery.html').write_text('<!doctype html><meta charset="utf-8"><title>片尾方案</title><style>body{margin:0;background:#0b0e0d;color:#fff;font:16px system-ui;padding:32px}.g{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}figure{margin:0;background:#171b19;padding:12px;border-radius:16px}img{width:100%;border-radius:10px}</style><h1>Qiaomu Screen2Video · 片尾方案</h1><div class="g">'+tiles+'</div>')
 print(project/'outro-gallery.html')

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('--variants',action='store_true',help='同时生成 16:9 与 9:16 可复用片尾');a=ap.parse_args();make(a.project.expanduser().resolve(),a.variants)
