import json,subprocess,sys,wave
import numpy as np
VAR=sys.argv[1]
SPEED=float(sys.argv[2]) if len(sys.argv)>2 else 1.4
FF="/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
segs=json.load(open("t.json"))["segments"]
exec(open("texts.py").read());exec(open("texts_en.py").read())
assert len(T)==len(segs)==len(EN),(len(T),len(segs),len(EN))
TTS={6,7,8,14,28,29,30}
TTS_RANGES=[(18.6,26.4),(42.0,45.0),(77.4,86.6)]
ZOOM=[]
COLD=(42.0,45.0)
INK="&H000000&";CREAM="&HFFFFFF&";VERM="&HFF9132&";ACCL="&HF37000&";GRAY="&HD4D4D4&";DIM="&H7A7A7A&";HAIR="&H333333&";WHITE="&HFFFFFF&"
PX,PY,PW,PH=217,22,1486,836
iv=[]
for s in segs:
    a,b=max(0,s["start"]-0.08),s["end"]+0.18
    if iv and a-iv[-1][1]<0.25: iv[-1][1]=b
    else: iv.append([a,b])
iv[-1][1]=min(iv[-1][1],164.6)
bounds=sorted({x for r in TTS_RANGES for x in r}|{x for z in ZOOM for x in z[:2]})
pieces=[]
for a,b in iv:
    cuts=sorted({a,b}|{t for t in bounds if a<t<b})
    for x,y in zip(cuts,cuts[1:]):
        m=(x+y)/2
        sp=1.0 if any(r0<=m<=r1 for r0,r1 in TTS_RANGES) else SPEED
        z=next(((zz[2],zz[3],zz[4]) for zz in ZOOM if zz[0]<=m<=zz[1]),(1,.5,.5))
        pieces.append((x,y,sp,z))
pieces.insert(0,(COLD[0],COLD[1],1.0,(1,.5,.5)))
ns=[];acc=0
for a,b,sp,z in pieces: ns.append(acc);acc+=(b-a)/sp
TOTAL_V=acc;MAIN0=ns[1]
def mp(t):
    for (a,b,sp,z),n in list(zip(pieces,ns))[1:]:
        if a-1e-6<=t<=b+1e-6: return n+(t-a)/sp
    for (a,b,sp,z),n in list(zip(pieces,ns))[1:]:
        if t<a: return n
    return TOTAL_V
# reading-speed check
bad=[]
for i,(s,t) in enumerate(zip(segs,T),1):
    sp=1.0 if i in TTS else SPEED
    d=(s["end"]-s["start"]+0.1)/sp
    cps=len([c for c in t if c.strip() and c not in "，。、：「」"])/d
    if cps>9.5: bad.append((i,round(cps,1),t))
badE=[]
for i,(s_,e_) in enumerate(zip(segs,EN),1):
    sp_=1.0 if i in TTS else SPEED
    d_=(s_["end"]-s_["start"]+0.1)/sp_
    c_=len(e_)/d_
    if c_>22: badE.append((i,round(c_,1),e_))
print("fast cues:",bad);print("fast EN cues:",badE)
OUT=6.5 if VAR=="A" else 1.0
TOTAL=TOTAL_V+OUT
def ts(t):
    t=max(t,0);h=int(t//3600);m=int(t%3600//60);s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
KW=["播放","音色","豆包","本地","系统自带","OpenAI 兼容","密钥","日记","原文","读者提交","分享到乔木 RSS","OPML","7000","听文章"]
def hl(t):
    for k in KW: t=t.replace(k,"{\\c"+VERM+"}"+k+"{\\c"+GRAY+"}")
    return t
SANS="LXGW Neo XiHei";SERIF="Songti SC";MONO="Menlo";DID="Didot"
def sty(n,font,size,col,bold=0,ital=0,al=5,sp=0,bs=1,out=0,ocol="&H00000000&"):
    return f"Style: {n},{font},{size},{col},{col},{ocol},&H00000000,{bold},{ital},0,0,100,100,{sp},0,{bs},{out},0,{al},0,0,0,1"
hdr="""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
"""+"\n".join([
 sty("Sub",SANS,52,GRAY,sp=0.5),
 sty("Quote",SERIF,52,CREAM,bold=0),
 f"Style: Karaoke,{SERIF},198,{INK},&HDCDCDC&,&H00000000&,&H00000000&,1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
 sty("En","Atkinson Hyperlegible Next SemiBold",34,"&HB4B4B4&",sp=0.2),
 sty("Lbl",SANS,20,DIM,sp=0.5,al=4),
 sty("Slate",SERIF,34,INK,bold=1,al=7,bs=3,out=14,ocol=CREAM),
 sty("Dr",SANS,20,WHITE,al=7),
 sty("Serif",SERIF,60,INK,bold=1),
 sty("Mono",MONO,22,INK,sp=4),
 sty("Did",DID,44,INK,ital=1),
 sty("Sans",SANS,30,INK),
])+"\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
ev=[]
import re,math
RISE={"En":(10,0.18),"Sub":(10,0.16),"Quote":(10,0.16),"Serif":(22,0.42),"Did":(16,0.42)}
def _line(a,b,st,tx,layer): ev.append(f"Dialogue: {layer},{ts(a)},{ts(b)},{st},,0,0,0,,{tx}")
def E(a,b,st,tx,layer=1):
    m=re.search(r"\\pos\((-?[\d.]+),(-?[\d.]+)\)",tx);fm=re.search(r"\\fad\((\d+),(\d+)\)",tx)
    if st in RISE and m and fm and tx.startswith("{") and b-a>0.25:
        x=float(m.group(1));y=float(m.group(2));fo=int(fm.group(2))/1000
        dy,dur=RISE[st]
        body=tx.replace(m.group(0),"").replace(fm.group(0),"")
        j=body.index("}")
        tags,text=body[1:j],body[j+1:]
        tags_no1a=re.sub(r"\\1a&H[0-9A-F]{2}&","",tags)
        n=max(1,int(dur*30));orig=re.search(r"\\1a&H([0-9A-F]{2})&",tags);ob=int(orig.group(1),16) if orig else 0
        for k in range(n):
            u=(k+1)/n;e=1-2**(-10*u) if u<1 else 1.0
            t0=a+k/30;t1=min(a+(k+1)/30,b)
            if t0>=b: break
            al=max(ob,int(255*(1-min(1,e*1.25))))
            _line(t0,t1,st,"{"+f"\\pos({x:.1f},{y+dy*(1-e):.1f})\\1a&H{al:02X}&"+tags_no1a+"}"+text,layer)
        t_hold=a+n/30;t_end=b-fo
        if t_end>t_hold: _line(t_hold,t_end,st,"{"+f"\\pos({x:.1f},{y})"+tags+"}"+text,layer)
        if fo>0: _line(max(t_hold,t_end),b,st,"{"+f"\\pos({x:.1f},{y})\\fad(0,{int(fo*1000)})"+tags+"}"+text,layer)
        return
    _line(a,b,st,tx,layer)
def rect(a,b,x,y,w,h,col,alpha="00",layer=10,extra=""):
    E(a,b,"Dr",f"{{\\an7\\pos({x},{y})\\c{col}\\1a&H{alpha}&\\bord0\\shad0{extra}\\p1}}m 0 0 l {w} 0 l {w} {h} l 0 {h}{{\\p0}}",layer)
def frame(a,b,x,y,w,h,fill,line,layer=10,extra=""):
    E(a,b,"Dr",f"{{\\an7\\pos({x},{y})\\c{fill}\\3c{line}\\bord1.5\\shad0{extra}\\p1}}m 0 0 l {w} 0 l {w} {h} l 0 {h}{{\\p0}}",layer)
def corner(cx,cy,fx,fy,R=14):
    k=0.4477*R
    P=[(0,0),(R,0),("b",k,0,0,k,0,R)]
    def t(x,y): return (R-x if fx else x, R-y if fy else y)
    (x0,y0)=t(0,0);(x1,y1)=t(R,0);(c1x,c1y)=t(k,0);(c2x,c2y)=t(0,k);(x2,y2)=t(0,R)
    path=f"m {x0} {y0} l {x1} {y1} b {c1x} {c1y} {c2x} {c2y} {x2} {y2} l {x0} {y0}"
    E(0,TOTAL,"Dr",f"{{\\an7\\pos({cx},{cy})\\c{INK}\\bord0\\shad0\\p1}}{path}{{\\p0}}",6)
# --- subtitles in the band
cd=COLD[1]-COLD[0]
for i,(s,t) in enumerate(zip(segs,T),1):
    a,b=mp(s["start"]),mp(s["end"]+0.1)
    nxt=mp(segs[i]["start"])-0.04 if i<len(segs) else TOTAL_V
    b=max(b,min(a+len(EN[i-1])/19,nxt))
    if i in TTS: E(a,b,"Quote","{\\fad(70,70)\\pos(960,912)}「"+t+"」",5)
    else: E(a,b,"Sub","{\\fad(70,70)\\pos(960,912)}"+hl(t),5)
    E(a,b,"En","{\\fad(70,70)\\pos(960,964)}"+EN[i-1],5)
# --- plate corners
for cx,cy,fx,fy in [(PX,PY,0,0),(PX+PW-14,PY,1,0),(PX,PY+PH-14,0,1),(PX+PW-14,PY+PH-14,1,1)]: corner(cx,cy,fx,fy)
# --- chapters + progress (pill tabs)
CH=[("听文章",0.7),("换音色",33.2),("三步配置",61.4),("选段朗读",68.7),("记笔记",91.4),("订阅·投稿",105.4)]
DESC=["任何一篇文章，一键念出来","豆包 · 本地 · 系统自带 · OpenAI 兼容","申请密钥  →  填入  →  保存","选中任意一段，从这里开始读","一键写入今天的日记，附原文链接","信息源 · OPML 导入 · 读者提交（彩蛋）"]
cb=[MAIN0]+[mp(t) for _,t in CH[1:]]+[TOTAL_V]
N=len(CH);GAP=8;usable=PW-GAP*(N-1);span=cb[-1]-cb[0]
wid=[usable*(0.4*(cb[i+1]-cb[i])/span+0.6/N) for i in range(N)]
xs=[];x=PX
for w in wid: xs.append(x);x+=w+GAP
def rr(w,h,r):
    k=0.5523*r
    return (f"m {r} 0 l {w-r} 0 b {w-r+k:.1f} 0 {w} {r-k:.1f} {w} {r} l {w} {h-r} b {w} {h-r+k:.1f} {w-r+k:.1f} {h} {w-r} {h} "
            f"l {r} {h} b {r-k:.1f} {h} 0 {h-r+k:.1f} 0 {h-r} l 0 {r} b 0 {r-k:.1f} {r-k:.1f} 0 {r} 0")
def drawing(a,b,x,y,path,col,alpha="00",layer=10,extra=""):
    E(a,b,"Dr",f"{{\\an7\\pos({x},{y})\\c{col}\\1a&H{alpha}&\\bord0\\shad0{extra}\\p1}}{path}{{\\p0}}",layer)
LY=1058
DOT="m 0 6 b 0 2.7 2.7 0 6 0 b 9.3 0 12 2.7 12 6 b 12 9.3 9.3 12 6 12 b 2.7 12 0 9.3 0 6"
for i,((name,_),x,w) in enumerate(zip(CH,xs,wid)):
    a,b=cb[i],cb[i+1];x=round(x);w=round(w);dur=int((b-a)*1000)
    rect(cb[0],TOTAL_V,x,LY-2,w,4,HAIR,"00",9,"\\fad(300,300)")
    E(a,TOTAL_V,"Dr",f"{{\\an7\\pos({x},{LY-2})\\c{WHITE}\\bord0\\shad0\\fscx0\\t(0,{dur},\\fscx100)\\p1}}m 0 0 l {w} 0 l {w} 4 l 0 4{{\\p0}}",10)
    E(a,b,"Dr",f"{{\\an7\\move({x-6},{LY-6},{x+w-6},{LY-6},0,{dur})\\c{VERM}\\3c&H000000&\\bord2\\shad0\\fad(120,150)\\p1}}{DOT}{{\\p0}}",12)
    lab=f"{{\\fnMenlo\\fs21}}{i+1:02d}{{\\fn{SANS}\\fs25}}   {name}"
    E(cb[0],TOTAL_V,"Lbl",f"{{\\an4\\pos({x},1030)\\c&H777777&\\fad(300,300)}}"+lab,11)
    E(a,TOTAL_V,"Lbl",f"{{\\an4\\pos({x},1030)\\c{WHITE}\\fad(150,0)}}"+lab,12)
    # intro: detached card (inset, rounded, hairline border, soft shadow), eased rise + fade
    ss=a+(0.15 if i==0 else 0);se=ss+2.8
    x0,y0,cw,ch=PX+28,PY+28,540,164
    IN=0.32;OUTD=0.22;FR=1/30
    def vis(t):
        if t<ss or t>=se: return 0.0,0.0
        if t<ss+IN:
            u=(t-ss)/IN;e=1-2**(-10*u);return min(1,e*1.2),14*(1-e)
        if t>se-OUTD:
            u=(t-(se-OUTD))/OUTD;return 1-u,-8*u**3
        return 1.0,0.0
    def lay(kind,x,y,body,layer,base=0,delay=0.0):
        t=ss
        steps=[]
        while t<se-1e-6:
            v,dy=vis(t-delay if t-delay>=ss else ss-1)
            if t<ss+IN+delay or t>=se-OUTD:
                steps.append((t,min(t+FR,se),v,dy));t+=FR
            else:
                steps.append((t,se-OUTD,1.0,0.0));t=se-OUTD
        for t0,t1,v,dy in steps:
            al=int(255-(255-base)*v)
            tx=f"\\pos({x},{y+dy:.1f})\\1a&H{al:02X}&"
            if kind=="shape": E(t0,t1,"Dr",f"{{\\an7{tx}\\c{body[1]}\\bord0\\shad0{body[2]}\\p1}}{body[0]}{{\\p0}}",layer)
            else: E(t0,t1,body[0],f"{{\\an4{tx}{body[1]}}}{body[2]}",layer)
    lay("shape",x0,y0+10,(rr(cw,ch,16),"&H000000&","\\blur14"),13,0x78)
    lay("shape",x0-1,y0-1,(rr(cw+2,ch+2,17),"&H4A4A4A&",""),14,0x00)
    lay("shape",x0,y0,(rr(cw,ch,16),"&H0A0A0A&",""),15,0x00)
    lay("text",x0+30,y0+34,("Mono",f"\\fs22\\c{VERM}",f"{i+1:02d} / {N:02d}"),16,0,0.03)
    lay("text",x0+30,y0+86,("Serif",f"\\fs50\\b1\\c{WHITE}",name),16,0,0.06)
    lay("text",x0+30,y0+136,("Sans",f"\\fs23\\c&HB5B5B5&",DESC[i]),16,0,0.10)
def blob(a,b,cx,cy,r,col,alpha,blur,layer=41,extra=""):
    k=0.5523*r
    path=f"m {-r} 0 b {-r} {-k} {-k} {-r} 0 {-r} b {k} {-r} {r} {-k} {r} 0 b {r} {k} {k} {r} 0 {r} b {-k} {r} {-r} {k} {-r} 0"
    E(a,b,"Dr",f"{{\\an7\\pos({cx},{cy})\\c{col}\\1a&H{alpha}&\\bord0\\shad0\\blur{blur}{extra}\\p1}}{path}{{\\p0}}",layer)
L=160;Rr=1760
# --- cold open: one giant line, lit word by word in sync with the voice
rect(0,cd,0,0,1920,1080,CREAM,"00",40,"\\fad(0,300)")
def kline(y,parts):
    out="";cur=0.0
    for tx,s_,e_ in parts:
        gap=max(0,round((s_-cur)*100))
        if gap: out+="{\\k%d}"%gap
        out+="{\\kf%d}%s"%(max(1,round((e_-s_)*100)),tx);cur=e_
    E(0,cd,"Karaoke","{\\an4\\fad(200,300)\\pos(150,%d)}"%y+out,42)
kline(280,[("你",.08,.30),("好",.30,.52),("，",.52,.62)])
kline(530,[("现",.80,.88),("在",.88,.96),("可",.96,1.09),("以",1.09,1.22),("在",1.22,1.40),(" RSS",1.40,1.88)])
kline(780,[("中",1.88,2.10),("听",2.10,2.26),("文",2.26,2.44),("章",2.44,2.54),("了",2.54,2.68)])
E(0.2,cd,"En","{\\an4\\fad(300,300)\\fs36\\pos(160,940)}Hello — you can now listen to articles in RSS.",42)
E(0.2,cd,"Sans","{\\an4\\fad(300,300)\\fs22\\pos(160,1010)\\1a&H60&}乔木 AI RSS   ·   2026.10.16",42)
E(0.2,cd,"Sans","{\\an6\\fad(300,300)\\fs22\\pos(1760,1010)\\1a&H60&}刘飞 2.0   ·   朗读",42)
# --- outro
OS=TOTAL_V
if VAR=="A":
    rect(OS,TOTAL,0,0,1920,1080,CREAM,"00",40,"\\fad(500,0)")
    rect(OS+0.4,TOTAL,L,96,1600,1,INK,"00",41,"\\fad(300,0)")
    E(OS+0.5,TOTAL,"Mono","{\\an4\\fad(300,0)\\pos(160,138)\\1a&H40&}OBSIDIAN  —  COMMUNITY PLUGINS",42)
    E(OS+0.6,TOTAL,"Serif","{\\an4\\fad(350,0)\\fs128\\pos(150,290)}去插件市场，搜索",42)
    frame(OS+0.9,TOTAL,L,400,1100,104,"&HFFFFFF&",INK,42,"\\fad(300,0)")
    E(OS+1.1,OS+1.7,"Sans","{\\an4\\pos(200,452)\\fs34\\1a&H80&\\fad(150,0)}Search community plugins…",43)
    word="qiaomu"
    for k in range(1,len(word)+1):
        a=OS+1.7+0.14*(k-1); b=OS+1.7+0.14*k if k<len(word) else TOTAL
        E(a,b,"Sans","{\\an4\\pos(200,452)\\fs44}"+word[:k]+("{\\c"+ACCL+"}|" if k<len(word) else ""),43)
    c0=OS+3.2
    frame(c0,TOTAL,L,540,1100,176,"&HFFFFFF&",INK,42,"\\fad(350,0)")
    E(c0,TOTAL,"Serif","{\\fad(350,0)\\an4\\pos(200,596)\\fs46}Qiaomu AI RSS",43)
    E(c0,TOTAL,"Sans","{\\fad(350,0)\\an4\\pos(200,660)\\fs26\\1a&H60&}在 Obsidian 里读 RSS，还能听文章",43)
    rect(c0+0.2,TOTAL,1060,590,170,62,INK,"00",43,"\\fad(350,0)")
    E(c0+0.2,TOTAL,"Sans","{\\fad(350,0)\\pos(1145,621)\\c"+CREAM+"\\fs28}安装",44)
    a=OS+4.2
    rect(a,TOTAL,1370,400,1,316,INK,"00",41,"\\fad(300,0)")
    E(a,TOTAL,"Serif","{\\an4\\fad(400,0)\\fs52\\pos(1420,440)}向阳乔木",42)
    for j,tx in enumerate(["X   @vista8","GitHub   @joeseesun","qiaomu.ai"]):
        E(a+0.15+0.1*j,TOTAL,"Mono","{\\an4\\fad(400,0)\\fs26\\pos(1420,%d)\\1a&H20&}%s"%(520+54*j,tx),42)
    E(a+0.5,TOTAL,"Sans","{\\an4\\fad(400,0)\\fs26\\pos(1420,%d)\\1a&H40&}公众号「向阳乔木推荐看」"%(520+54*3),42)
    rect(OS+0.4,TOTAL,L,950,1600,1,INK,"00",41,"\\fad(300,0)")
    E(OS+0.6,TOTAL,"Mono","{\\an4\\fad(300,0)\\fs20\\pos(160,1005)\\1a&H50&}Settings › Community plugins › Browse",42)
rect(TOTAL-0.7,TOTAL,0,0,1920,1080,INK,"00",90,"\\fad(700,0)")
open(f"sub3_{VAR}.ass","w").write(hdr+"\n".join(ev)+"\n")
# --- graph
vf=[];af=[];n=len(pieces)
for i,(a,b,sp,(z,cx,cy)) in enumerate(pieces):
    crop="" if z==1 else f",crop=iw/{z}:ih/{z}:(iw-iw/{z})*{cx}:(ih-ih/{z})*{cy}"
    vf.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=(PTS-STARTPTS)/{sp}{crop},scale={PW*2}:{PH*2},setsar=1,fps=30[v{i}]")
    d=(b-a)/sp
    at="" if sp==1 else f",atempo={sp}"
    af.append(f"[1:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS{at},afade=t=in:d=0.02,afade=t=out:st={d-0.02:.3f}:d=0.02[a{i}]")
cat="".join(f"[v{i}][a{i}]" for i in range(n))
g=";".join(vf+af)+f";{cat}concat=n={n}:v=1:a=1[vc][ac];[vc]tpad=stop_mode=clone:stop_duration={OUT},pad=3840:2160:{PX*2}:{PY*2}:color=0x000000[vt];[vt]ass=sub3_{VAR}.ass:fontsdir=fonts[v];[ac]loudnorm=I=-17:TP=-1.5:LRA=11,apad=pad_dur={OUT}[a]"
open(f"graph3_{VAR}.txt","w").write(g)
print(VAR,"speed",SPEED,"video",round(TOTAL_V,1),"total",round(TOTAL,1))
subprocess.run([FF,"-y","-v","error","-i","plate4k.mp4","-i","proxy.mp4","-/filter_complex",f"graph3_{VAR}.txt","-map","[v]","-map","[a]","-t",f"{TOTAL:.2f}","-c:v","libx264","-preset","medium","-crf","17","-profile:v","high","-level","5.1","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",f"v4k_{VAR}.mp4"],check=True)
sr=44100;n_=int(sr*TOTAL);fx=np.zeros(n_)
for c in cb[:-1]:
    i=int(c*sr);m=int(0.5*sr);tt=np.arange(m)/sr
    d=(np.sin(2*np.pi*1046*tt)+0.25*np.sin(2*np.pi*2093*tt))*np.exp(-tt*10)*0.5
    fx[i:i+m]+=d[:max(0,min(m,n_-i))]
w=wave.open("fx.wav","wb");w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((fx*0.5*32767).astype(np.int16).tobytes());w.close()
fo=TOTAL-3.5
mix=(f"[1:a]atrim=0:{TOTAL:.2f},volume=0.15,lowpass=f=3200,afade=t=in:d=2,afade=t=out:st={fo:.2f}:d=3.2[m];"
 f"[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=500[md];"
 f"[2:a]volume=0.10[f];[v][md][f]amix=inputs=3:duration=first:normalize=0,alimiter=limit=0.9,afade=t=out:st={TOTAL-0.7:.2f}:d=0.7[a]")
subprocess.run([FF,"-y","-v","error","-i",f"v4k_{VAR}.mp4","-i","bed.wav","-i","fx.wav","-filter_complex",mix,"-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",f"final4k_{VAR}.mp4"],check=True)
