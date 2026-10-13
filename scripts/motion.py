#!/usr/bin/env python3
"""Validate semantic motion plans and render ASS overlays plus original light SFX."""
import argparse, json, math, random, re, struct
from pathlib import Path

import s2v

VISUAL_TYPES={"word_highlight","keyword","callout","chapter","sticker"}
ANCHORS={"top-left","top-center","top-right","middle-left","middle-right"}
SFX={"none","pop","click","whoosh","chime"}
DEFAULT_SFX={"word_highlight":"none","keyword":"pop","callout":"click","chapter":"whoosh","sticker":"pop"}
KEYWORD_STYLES={"label","stroke","card","brand","douyin"}  # douyin = legacy alias of stroke
FLOWER_EM=1000/(1160+288)  # libass maps fs to winAscent+winDescent of Noto Sans SC
# sticker centre (x, y) in frame units; never the bottom subtitle zone
STICKER_ANCHORS={"top-left":(.13,.2),"top-center":(.5,.2),"top-right":(.87,.2),"middle-left":(.13,.46),"middle-right":(.87,.46)}
DEFAULT_DISPLAY={"keyword":1.3,"sticker":1.5}
ACCENT_ASS="&H003C5AF0&"  # #F05A3C, ASS stores BGR.
INK_ASS="&H00131511&"     # #111513.
WARM_ASS="&H00E8F0F5&"    # #F5F0E8.


def _number(value,label):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(label+" 必须是有限数字")
 return float(value)


def _text(value,label,max_chars):
 if not isinstance(value,str) or not value.strip():raise ValueError(label+" 不能为空")
 value=value.strip()
 if len(value)>max_chars:raise ValueError(f"{label} 过长，最多 {max_chars} 个字符")
 return value


def _word_text(word):
 return str(word.get("word",word.get("text",""))).strip()


def _norm(value):
 return re.sub(r"[\s，。！？、,.!?：:；;（）()《》<>‘’“”\-]","",value).lower()


def _chapter_reading_seconds(title,subtitle=""):
 """Estimate final-timeline reading time for a bilingual chapter card."""
 title_units=len(re.sub(r"\s+","",title))
 subtitle_units=len(re.sub(r"\s+","",subtitle or ""))
 language_time=max(title_units/7.0,subtitle_units/17.0)
 return round(min(4.0,max(2.2,language_time+.8)),2)


def _resolve_word_timing(event,cue,raw_cue):
 if "start" in event and "end" in event:return _number(event["start"],"start"),_number(event["end"],"end")
 target=_norm(event["text"]);words=raw_cue.get("words",[]) if raw_cue else []
 if not isinstance(words,list) or not words:raise ValueError(event["id"]+": 缺少逐词时间；请为高亮提供 start/end，或换用带词时间戳的 ASR")
 for i in range(len(words)):
  joined=""
  for j in range(i,min(len(words),i+12)):
   joined+=_norm(_word_text(words[j]))
   if joined==target:
    return _number(words[i]["start"],"word.start"),_number(words[j]["end"],"word.end")
   if len(joined)>len(target):break
 raise ValueError(event["id"]+": 在原始逐词转写中找不到高亮文字 "+event["text"])


def flower_font():
 """Heavy display face for 花字: Noto Sans SC Black (OFL), instanced once from the cached variable font."""
 cache=Path.home()/".cache/qiaomu-screen2video/fonts";out=cache/"NotoSansSC-Black.ttf"
 if out.is_file():return out
 src=cache/"notosanssc-variable.ttf"
 if not src.is_file():raise FileNotFoundError("缺少 Noto Sans SC 可变字体；先运行 scripts/fonts.py")
 from fontTools.ttLib import TTFont
 from fontTools.varLib import instancer
 tmp=out.with_suffix(".part");instancer.instantiateVariableFont(TTFont(src),{"wght":900},updateFontNames=True).save(tmp);tmp.replace(out)
 return out


def _rrect(x,y,w,h,r):
 k=.5523*r
 return (f"m {x+r:.0f} {y:.0f} l {x+w-r:.0f} {y:.0f} b {x+w-r+k:.0f} {y:.0f} {x+w:.0f} {y+r-k:.0f} {x+w:.0f} {y+r:.0f} "
         f"l {x+w:.0f} {y+h-r:.0f} b {x+w:.0f} {y+h-r+k:.0f} {x+w-r+k:.0f} {y+h:.0f} {x+w-r:.0f} {y+h:.0f} "
         f"l {x+r:.0f} {y+h:.0f} b {x+r-k:.0f} {y+h:.0f} {x:.0f} {y+h-r+k:.0f} {x:.0f} {y+h-r:.0f} "
         f"l {x:.0f} {y+r:.0f} b {x:.0f} {y+r-k:.0f} {x+r-k:.0f} {y:.0f} {x+r:.0f} {y:.0f}")


def _emph(text,key,base,accent):
 if key and key in text:
  a,b=text.split(key,1)
  return f"{{\\1c{base}}}"+s2v.ass_text(a)+f"{{\\1c{accent}}}"+s2v.ass_text(key)+f"{{\\1c{base}}}"+s2v.ass_text(b)
 return s2v.ass_text(text)


def _flower_events(item,start,end,dur_ms,width,height,scale):
 """Three restrained presets, prototyped on real frames (2026-10-13):
 label  – vermilion rounded pill, white Black-weight text; pill wipes open from the left, text follows.
 stroke – white Black-weight text, one ink stroke + hard offset shadow, emphasis word in vermilion; 92→104→100 % pop.
 card   – warm card with ink outline and offset vermilion block, ink text, emphasis in vermilion; floats up, tilt 6°→2°.
 Rules: one heavy face, ≤2 colours + ink, no faux bold, no gradients, no stacked strokes."""
 from PIL import ImageFont
 style=item["style"];text=item["text"];key=item.get("emphasis");fam="Noto Sans SC Black";ev=[]
 size=round((104 if style=="stroke" else 84)*scale)
 tw=ImageFont.truetype(str(flower_font()),max(1,round(size*FLOWER_EM))).getlength(text)
 pad_x,pad_y=(0,0) if style=="stroke" else (31*scale,15*scale)
 w=tw+pad_x*2;h=size*FLOWER_EM*1.12+pad_y*2
 ax,ay=({"top-left":(.075,.11),"top-center":(.5,.11),"top-right":(.925,.11),"middle-left":(.075,.41),"middle-right":(.925,.41)})[item["anchor"]]
 x0=ax*width if ax<.3 else ax*width-w/2 if ax==.5 else ax*width-w;y0=ay*height;cy=y0+h/2
 out=f"\\fad(0,{min(170,dur_ms//3)})"
 if style=="label":
  wipe=f"\\org({x0:.0f},{cy:.0f})\\fscx0\\t(0,{min(230,dur_ms)},0.45,\\fscx100)"
  ev.append((4,f"{{\\an7\\pos(0,0)\\p1\\1c&H000000&\\1a&HB4&\\bord0\\blur{10*scale:.0f}{wipe}{out}}}"+_rrect(x0+5*scale,y0+9*scale,w,h,h*.22)))
  ev.append((5,f"{{\\an7\\pos(0,0)\\p1\\1c{ACCENT_ASS}\\bord0{wipe}{out}}}"+_rrect(x0,y0,w,h,h*.22)))
  ev.append((6,f"{{\\an4\\pos({x0+pad_x:.0f},{cy:.0f})\\fn{fam}\\fs{size}\\1c&H00FFFFFF&\\bord0\\shad0\\alpha&HFF&\\t({min(170,dur_ms)},{min(300,dur_ms)},\\alpha&H00&){out}}}"+s2v.ass_text(text)))
 elif style=="stroke":
  cx=x0+w/2;pop=f"\\fscx92\\fscy92\\t(0,{min(120,dur_ms)},\\fscx104\\fscy104)\\t({min(120,dur_ms)},{min(220,dur_ms)},\\fscx100\\fscy100)"
  ev.append((6,f"{{\\an5\\pos({cx:.0f},{cy:.0f})\\fn{fam}\\fs{size}\\3c{INK_ASS}\\bord{7*scale:.1f}\\4c{INK_ASS}\\4a&H00&\\xshad{5*scale:.1f}\\yshad{6*scale:.1f}\\fad(60,{min(170,dur_ms//3)}){pop}}}"+_emph(text,key,"&H00FFFFFF&",ACCENT_ASS)))
 else:
  d=18*scale;org=f"\\org({x0+w/2:.0f},{cy:.0f})\\frz6\\t(0,{min(240,dur_ms)},0.6,\\frz2)"
  mv=lambda x,y:f"\\move({x:.0f},{y+d:.0f},{x:.0f},{y:.0f},0,{min(240,dur_ms)})"
  fade=f"\\fad(90,{min(170,dur_ms//3)})"
  ev.append((4,f"{{\\an7{mv(0,0)}\\p1\\1c{ACCENT_ASS}\\bord0{org}{fade}}}"+_rrect(x0+10*scale,y0+10*scale,w,h,10*scale)))
  ev.append((5,f"{{\\an7{mv(0,0)}\\p1\\1c{WARM_ASS}\\3c{INK_ASS}\\bord{3*scale:.1f}{org}{fade}}}"+_rrect(x0,y0,w,h,10*scale)))
  ev.append((6,f"{{\\an4{mv(x0+pad_x,cy)}\\fn{fam}\\fs{size}\\bord0\\shad0{org}{fade}}}"+_emph(text,key,INK_ASS,ACCENT_ASS)))
 return [_dialogue(layer,start,end,"Flower",body) for layer,body in ev]


def _pop_rect(event,aspect=16/9):
 """Approximate normalised rect of a keyword/sticker, for occlusion checks."""
 if event["type"]=="sticker":
  cx,cy=STICKER_ANCHORS[event["anchor"]];h=event["size"];w=h/aspect
  return (cx-w/2,cy-h/2,w,h)
 x,y,_=({"top-left":(.075,.13,7),"top-center":(.5,.13,8),"top-right":(.925,.13,9),"middle-left":(.075,.43,7),"middle-right":(.925,.43,9)})[event["anchor"]]
 w=min(.6,.045*len(event["text"]));h=.09
 left=x if x<.3 else x-w/2 if x==.5 else x-w
 return (left,y,w,h)


def _occlusion_warnings(project,events,speed):
 """Use visual.py OCR (if run) to flag pops that sit on top of UI text the viewer is reading."""
 path=Path(project)/"work/visual-analysis.json"
 if not path.exists() or not events:return []
 data=s2v.read(path);frames=data.get("ocr") or [];out=[]
 for e in events:
  near=[f for f in frames if e["start"]-1<=f["t"]<=e["end"]+1]
  if not near:continue
  x,y,w,h=_pop_rect(e);area=max(w*h,1e-6);worst=0.0
  for f in near:
   cover=0.0
   for it in f["items"]:
    bx,by,bw,bh=it["box"];ix=max(0,min(x+w,bx+bw)-max(x,bx));iy=max(0,min(y+h,by+bh)-max(y,by));cover+=ix*iy
   worst=max(worst,cover/area)
  if worst>.2:out.append(e["id"]+f": 位置与屏幕文字重叠约 {worst:.0%}，可能遮住正在讲的界面；换 anchor 或缩小")
 return out


def validate_plan(project,write_qa=True):
 project=Path(project);m=s2v.read(project/"project.json");duration=float(m["media"]["duration"]);config=s2v.settings(project);speed=config["speed"]
 path=project/"motion-plan.json"
 if not path.exists():
  result={"schema":1,"profile":"balanced","events":[],"warnings":["尚未生成 motion-plan.json；基础字幕仍可渲染"]}
  if write_qa:s2v.write(project/"output/motion-qa.json",result)
  return result
 plan=s2v.read(path)
 if not isinstance(plan,dict) or plan.get("schema")!=1 or not isinstance(plan.get("events"),list):raise ValueError("motion-plan.json 必须使用 schema 1 和 events 数组")
 if len(plan["events"])>200:raise ValueError("动效事件过多；单个视频最多 200 个")
 captions=s2v.normalize_cues(s2v.read(project/"captions.json"),duration,True)
 cue_map={x["id"]:x for x in captions};raw=s2v.read(project/"transcript.raw.json");raw_map={x["id"]:x for x in raw.get("segments",[])}
 ids=set();events=[];warnings=[]
 for index,item in enumerate(plan["events"]):
  if not isinstance(item,dict):raise ValueError(f"events[{index}] 必须是对象")
  event=dict(item);event["id"]=str(event.get("id",f"m{index+1:04}"))
  if event["id"] in ids:raise ValueError("重复动效 ID: "+event["id"])
  ids.add(event["id"]);kind=event.get("type")
  if kind not in VISUAL_TYPES:raise ValueError(event["id"]+": 未知动效类型")
  if not isinstance(event.get("enabled",True),bool):raise ValueError(event["id"]+": enabled 必须为布尔值")
  event["enabled"]=event.get("enabled",True);event["reason"]=str(event.get("reason",""))[:120]
  if kind=="word_highlight":
   cue_id=str(event.get("cue_id",""));cue=cue_map.get(cue_id)
   if not cue:raise ValueError(event["id"]+": cue_id 不存在")
   event["cue_id"]=cue_id;event["text"]=_text(event.get("text"),event["id"]+".text",24)
   if event["text"].lower() not in cue["zh"].lower():raise ValueError(event["id"]+": 高亮文字必须原样存在于中文字幕中")
   raw_cue=raw_map.get(cue_id)
   if raw_cue is None:
    # re-segmented cue (new id + parent_ids): borrow the real ASR words inside its time range
    raw_cue={"words":[w for seg in raw.get("segments",[]) for w in seg.get("words",[]) if isinstance(w,dict) and w.get("start",-1)>=cue["start"]-.05 and w.get("end",1e9)<=cue["end"]+.05]}
   start,end=_resolve_word_timing(event,cue,raw_cue)
   if start<cue["start"]-.025 or end>cue["end"]+.025:raise ValueError(event["id"]+": 高亮时间必须位于对应字幕范围内")
  elif kind in ("keyword","sticker") and event.get("at_word"):
   # Sync to the stressed word: appear ~60 ms before its onset (reads as "on the beat"), hold for a readable time.
   cue_id=str(event.get("cue_id",""));cue=cue_map.get(cue_id)
   if not cue:raise ValueError(event["id"]+": at_word 需要有效 cue_id")
   raw_cue=raw_map.get(cue_id) or {"words":[w for seg in raw.get("segments",[]) for w in seg.get("words",[]) if isinstance(w,dict) and w.get("start",-1)>=cue["start"]-.05 and w.get("end",1e9)<=cue["end"]+.05]}
   onset,_=_resolve_word_timing({"id":event["id"],"text":str(event["at_word"])},cue,raw_cue)
   start=max(0.0,onset-.06*speed);hold=_number(event.get("hold",DEFAULT_DISPLAY[kind]),event["id"]+".hold")
   end=_number(event["end"],event["id"]+".end") if "end" in event else start+hold*speed
   event["synced_word"]=str(event["at_word"])
  else:
   start=_number(event.get("start"),event["id"]+".start");end=_number(event.get("end"),event["id"]+".end")
  if start<0 or end<=start or end>duration+.15:raise ValueError(event["id"]+": 时间超出源视频范围")
  event["start"]=start;event["end"]=min(end,duration)
  display=(event["end"]-event["start"])/speed;event["display_seconds"]=round(display,3)
  if kind=="keyword":
   event["text"]=_text(event.get("text"),event["id"]+".text",18);event["anchor"]=event.get("anchor","top-left")
   if event["anchor"] not in ANCHORS:raise ValueError(event["id"]+": anchor 无效")
   if display<.7 or display>1.8:warnings.append(event["id"]+f": 花字最终可见 {display:.2f} 秒，建议 0.8–1.6 秒")
   event["style"]=event.get("style",plan.get("keyword_style","label"))
   if event["style"] not in KEYWORD_STYLES:raise ValueError(event["id"]+": style 只能是 label / stroke / card / brand")
   if event["style"]=="douyin":event["style"]="stroke"
   if event.get("emphasis") is not None:
    event["emphasis"]=str(event["emphasis"])
    if event["emphasis"] not in event["text"]:raise ValueError(event["id"]+": emphasis 必须是 text 的一部分")
  elif kind=="sticker":
   source=str(event.get("source",""))
   if not re.match(r"^(noto|fluent|memegen|file):.+",source):raise ValueError(event["id"]+": sticker.source 需为 noto:/fluent:/memegen:/file:")
   event["source"]=source;event["anchor"]=event.get("anchor","top-right")
   if event["anchor"] not in STICKER_ANCHORS:raise ValueError(event["id"]+": anchor 无效")
   event["size"]=_number(event.get("size",.24),event["id"]+".size")
   if not .1<=event["size"]<=.45:raise ValueError(event["id"]+": size 取画面高度的 0.1–0.45")
   if event.get("caption") is not None:event["caption"]=_text(event["caption"],event["id"]+".caption",16)
   event["tilt"]=_number(event.get("tilt",-4),event["id"]+".tilt")
   if display<.7 or display>2.4:warnings.append(event["id"]+f": 贴纸最终可见 {display:.2f} 秒，建议 0.8–2.0 秒")
  elif kind=="callout":
   target=event.get("target")
   if not isinstance(target,dict):raise ValueError(event["id"]+": callout 需要 target")
   target={k:_number(target.get(k),event["id"]+".target."+k) for k in ("x","y","w","h")}
   if target["x"]<0 or target["y"]<0 or target["w"]<=.005 or target["h"]<=.005 or target["x"]+target["w"]>1 or target["y"]+target["h"]>1:raise ValueError(event["id"]+": target 必须是 0–1 的归一化画面区域")
   event["target"]=target
   if event.get("label") is not None:event["label"]=_text(event["label"],event["id"]+".label",18)
   if target["y"]+target["h"]>.76:warnings.append(event["id"]+": 指示框进入字幕安全区，请抽帧检查")
   if display<1.1:warnings.append(event["id"]+f": 界面指引最终可见 {display:.2f} 秒，目标可能来不及定位")
  elif kind=="chapter":
   event["title"]=_text(event.get("title"),event["id"]+".title",24)
   if event.get("subtitle") is not None:event["subtitle"]=_text(event["subtitle"],event["id"]+".subtitle",50)
   recommended=_chapter_reading_seconds(event["title"],event.get("subtitle",""));event["recommended_display_seconds"]=recommended
   if display<1.8:raise ValueError(event["id"]+f": 章节卡在 {speed:g} 倍速成片中仅显示 {display:.2f} 秒；至少需要 1.8 秒，建议 {recommended:.2f} 秒")
   if display<recommended-.05:warnings.append(event["id"]+f": 章节卡最终可见 {display:.2f} 秒，按文字量建议 {recommended:.2f} 秒")
   if display>4.5:warnings.append(event["id"]+f": 章节卡最终可见 {display:.2f} 秒，检查是否拖慢节奏")
  event["sfx"]=event.get("sfx",DEFAULT_SFX[kind])
  if event["sfx"] not in SFX:raise ValueError(event["id"]+": sfx 无效")
  events.append(event)
 active=[e for e in events if e["enabled"] and e["type"]!="word_highlight"]
 active.sort(key=lambda x:(x["start"],x["end"]))
 for previous,current in zip(active,active[1:]):
  if current["start"]<previous["end"]-.08:warnings.append(previous["id"]+" 与 "+current["id"]+" 同时出现；建议一次只保留一个主视觉")
  if (current["start"]-previous["start"])/speed<1.5:warnings.append(current["id"]+": 成片时间距上一主视觉不足 1.5 秒，检查是否过密")
 pops=[e for e in active if e["type"] in ("keyword","sticker")]
 final_minutes=max(duration/speed/60,.25)
 if len(pops)/final_minutes>8:warnings.append(f"花字+贴纸每分钟 {len(pops)/final_minutes:.1f} 个，超过 8 个/分钟会显得吵；只留最重要的记忆点")
 stickers_=[e for e in pops if e["type"]=="sticker"]
 for previous,current in zip(stickers_,stickers_[1:]):
  if (current["start"]-previous["start"])/speed<6:warnings.append(current["id"]+": 两个贴纸间隔不足 6 秒，梗图重复太快会稀释笑点")
 warnings+=_occlusion_warnings(project,pops,speed)
 chapters=[e for e in active if e["type"]=="chapter"]
 if duration/speed<60 and len(chapters)>1:warnings.append(f"短于 60 秒的成片有 {len(chapters)} 张全屏章节卡；默认只保留 1 张，其余改用花字或界面指引")
 for previous,current in zip(chapters,chapters[1:]):
  gap=(current["start"]-previous["start"])/speed
  if gap<12:warnings.append(current["id"]+f": 与上一章节卡仅相隔 {gap:.1f} 秒，容易打断操作连续性")
 result={"schema":1,"profile":plan.get("profile","balanced"),"events":events,"warnings":warnings,"source":"motion-plan.json"}
 if write_qa:s2v.write(project/"output/motion-qa.json",result)
 return result


def _header(width,height,styles):
 return f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"+"\n".join(styles)+"\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"


def _dialogue(layer,start,end,style,text):
 return f"Dialogue: {layer},{s2v.stamp(start,True)},{s2v.stamp(end,True)},{style},,0,0,0,,{text}"


def _drawing(points):
 return "m "+" l ".join(f"{round(x)} {round(y)}" for x,y in points)


def _arrow_polygon(ax,ay,bx,by,width,head):
 dx=bx-ax;dy=by-ay;length=max(1,math.hypot(dx,dy));ux=dx/length;uy=dy/length;px=-uy;py=ux
 neckx=bx-ux*head;necky=by-uy*head
 return [(ax+px*width,ay+py*width),(neckx+px*width,necky+py*width),(neckx+px*head*.55,necky+py*head*.55),(bx,by),(neckx-px*head*.55,necky-py*head*.55),(neckx-px*width,necky-py*width),(ax-px*width,ay-py*width)]


def _highlight_markup(lines,target):
 for line_index,line in enumerate(lines):
  pos=line.lower().find(target.lower())
  if pos<0:continue
  result=[]
  for i,current in enumerate(lines):
   if i==line_index:
    a=s2v.ass_text(current[:pos]);b=s2v.ass_text(current[pos:pos+len(target)]);c=s2v.ass_text(current[pos+len(target):])
    result.append(r"{\alpha&HFF&}"+a+r"{\alpha&H00&\c"+ACCENT_ASS+"}"+b+r"{\alpha&HFF&}"+c)
   else:result.append(r"{\alpha&HFF&}"+s2v.ass_text(current))
  return r"\N".join(result)
 return None


def render_ass(project,resolved,width,height,band,intro,font_manifest):
 from PIL import ImageFont
 from fontTools.ttLib import TTFont
 c=s2v.settings(project);scale=height/1080;out_h=height+band;speed=c["speed"]
 zh=font_manifest["zh"];en=font_manifest["en"];zh_size=round(c["zh_size"]*scale)
 zh_chars="".join(str(e.get(k,"")) for e in resolved["events"] for k in ("text","label","title"));en_chars="".join(str(e.get("subtitle","")) for e in resolved["events"])
 for lang,chars,font_path in [("动效中文",zh_chars,zh["file"]),("章节英文",en_chars,en["file"])]:
  cmap=TTFont(font_path).getBestCmap();missing=sorted({ch for ch in chars if not ch.isspace() and ord(ch) not in cmap})
  if missing:raise ValueError(lang+"字体缺字: "+"".join(missing))
 styles=[
  f"Style: Highlight,{zh['family']},{zh_size},{ACCENT_ASS},{ACCENT_ASS},{INK_ASS},&H73000000,0,0,0,0,100,100,0,0,1,{2.55*scale:.2f},{1.1*scale:.2f},2,0,0,0,1",
  f"Style: Flower,{zh['family']},{round(72*scale)},{WARM_ASS},{WARM_ASS},{INK_ASS},&H66000000,-1,0,0,0,100,100,1,0,1,{3.2*scale:.2f},{1.3*scale:.2f},7,0,0,0,1",
  f"Style: Label,{zh['family']},{round(34*scale)},{WARM_ASS},{WARM_ASS},{INK_ASS},&H66000000,-1,0,0,0,100,100,0,0,1,{2.2*scale:.2f},{1.0*scale:.2f},7,0,0,0,1",
  f"Style: Chapter,{zh['family']},{round(76*scale)},{WARM_ASS},{WARM_ASS},{INK_ASS},&H55000000,-1,0,0,0,100,100,1,0,1,{2.5*scale:.2f},{1.0*scale:.2f},5,0,0,0,1",
  f"Style: ChapterSub,{en['family']},{round(34*scale)},{WARM_ASS},{WARM_ASS},{INK_ASS},&H77000000,-1,0,0,0,100,100,0,0,1,{1.5*scale:.2f},{.8*scale:.2f},5,0,0,0,1",
  "Style: Vector,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1"
 ]
 events=[];captions={x["id"]:x for x in s2v.normalize_cues(s2v.read(project/"captions.json"),s2v.read(project/"project.json")["media"]["duration"],True)}
 font=ImageFont.truetype(zh["file"],zh_size)
 for item in resolved["events"]:
  if not item["enabled"]:continue
  kind=item["type"];start=item["start"]/speed+intro;end=item["end"]/speed+intro;dur_ms=max(1,round((end-start)*1000))
  if kind=="word_highlight":
   if not c["word_highlight"]:continue
   cue=captions[item["cue_id"]];lines=s2v.wrap_text(cue["zh"],font,width*.88);markup=_highlight_markup(lines,item["text"])
   if markup is None:continue
   en_lines=s2v.wrap_text(cue["en"],ImageFont.truetype(en["file"],round(c["en_size"]*scale)),width*.88)
   bottom=out_h-round(height*.075);y=bottom-round(round(c["en_size"]*scale)*1.17*len(en_lines)+height*.004)
   events.append(_dialogue(20,start,end,"Highlight",f"{{\\an2\\pos({width//2},{y})\\fad(45,90)}}"+markup))
  elif kind=="keyword" and item.get("style","brand")!="brand":
   events.extend(_flower_events(item,start,end,dur_ms,width,height,scale))
  elif kind=="keyword":
   anchors={"top-left":(.075,.13,7),"top-center":(.5,.13,8),"top-right":(.925,.13,9),"middle-left":(.075,.43,7),"middle-right":(.925,.43,9)}
   x,y,align=anchors[item["anchor"]];x*=width;y*=height
   large=ImageFont.truetype(zh["file"],round(72*scale));bbox=large.getbbox(item["text"],stroke_width=max(1,round(3*scale)));tw=bbox[2]-bbox[0];th=bbox[3]-bbox[1];pad=round(12*scale)
   left=x-pad if align in (7,) else x-tw/2-pad if align==8 else x-tw-pad;top=y-pad*.6;right=left+tw+pad*2;bottom=top+th+pad*1.25
   block=_drawing([(left,top),(right,top),(right-8*scale,bottom),(left+8*scale,bottom)])
   events.append(_dialogue(4,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{ACCENT_ASS}\\1a&H12&\\bord0\\fad(100,140)}}{block}"))
   events.append(_dialogue(5,start,end,"Flower",f"{{\\an{align}\\pos({round(x)},{round(y)})\\fscx90\\fscy90\\fad(90,140)\\t(0,{min(180,dur_ms)},\\fscx100\\fscy100)}}"+s2v.ass_text(item["text"])))
  elif kind=="callout":
   t=item["target"];x1=t["x"]*width;y1=t["y"]*height;x2=(t["x"]+t["w"])*width;y2=(t["y"]+t["h"])*height;pad=max(5,round(min(width,height)*.009));x1-=pad;y1-=pad;x2+=pad;y2+=pad
   full=_drawing([(0,0),(width,0),(width,out_h),(0,out_h)])
   events.append(_dialogue(1,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{INK_ASS}\\1a&H72&\\bord0\\iclip({round(x1)},{round(y1)},{round(x2)},{round(y2)})\\fad(100,150)}}{full}"))
   box=_drawing([(x1,y1),(x2,y1),(x2,y2),(x1,y2)])
   events.append(_dialogue(2,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1a&HFF&\\3c{ACCENT_ASS}\\3a&H00&\\bord{max(3,round(5*scale))}\\fad(80,150)}}{box}"))
   cx=(x1+x2)/2;cy=(y1+y2)/2
   ax=x2+width*.11 if cx<width*.58 else x1-width*.11;ay=max(height*.1,min(height*.7,cy-height*.1));bx=x2 if cx<width*.58 else x1;by=cy
   arrow=_drawing(_arrow_polygon(ax,ay,bx,by,max(2,4*scale),max(10,18*scale)))
   events.append(_dialogue(3,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{ACCENT_ASS}\\1a&H00&\\bord0\\fad(100,150)}}{arrow}"))
   if item.get("label"):
    align=9 if cx<width*.58 else 7;events.append(_dialogue(4,start,end,"Label",f"{{\\an{align}\\pos({round(ax)},{round(ay-8*scale)})\\fad(100,150)}}"+s2v.ass_text(item["label"])))
  elif kind=="chapter":
   full=_drawing([(0,0),(width,0),(width,out_h),(0,out_h)])
   events.append(_dialogue(8,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{INK_ASS}\\1a&H78&\\bord0\\fad(180,260)}}{full}"))
   panel_w=min(width*.72,round(1160*scale));panel_h=round((245 if item.get("subtitle") else 190)*scale);panel_x=(width-panel_w)/2;panel_y=height*.5-panel_h/2
   panel=_drawing([(panel_x,panel_y),(panel_x+panel_w,panel_y),(panel_x+panel_w,panel_y+panel_h),(panel_x,panel_y+panel_h)])
   events.append(_dialogue(9,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{INK_ASS}\\1a&H28&\\3c{WARM_ASS}\\3a&HD8&\\bord{max(1,round(1.2*scale))}\\fad(180,260)}}{panel}"))
   bar_w=max(8,round(12*scale));bar_h=max(70,panel_h-round(72*scale));bar_x=panel_x+round(42*scale);bar_y=height*.5-bar_h/2
   bar=_drawing([(bar_x,bar_y),(bar_x+bar_w,bar_y),(bar_x+bar_w,bar_y+bar_h),(bar_x,bar_y+bar_h)])
   events.append(_dialogue(10,start,end,"Vector",f"{{\\an7\\pos(0,0)\\p1\\1c{ACCENT_ASS}\\bord0\\fad(180,260)}}{bar}"))
   text_x=bar_x+bar_w+round(38*scale);title_y=height*.5-(24*scale if item.get("subtitle") else 0)
   events.append(_dialogue(11,start,end,"Chapter",f"{{\\an4\\pos({round(text_x)},{round(title_y)})\\fad(180,260)\\fscx96\\fscy96\\t(0,{min(240,dur_ms)},\\fscx100\\fscy100)}}"+s2v.ass_text(item["title"])))
   if item.get("subtitle"):events.append(_dialogue(11,start,end,"ChapterSub",f"{{\\an4\\pos({round(text_x)},{round(height*.5+58*scale)})\\fad(210,260)}}"+s2v.ass_text(item["subtitle"])))
 path=Path(project)/"work/motion.ass";path.write_text(_header(width,out_h,styles)+"\n".join(events)+"\n")
 return path,len(events)


def _tone(kind,rate=48000):
 lengths={"pop":.12,"click":.055,"whoosh":.34,"chime":.42};n=round(lengths[kind]*rate);out=[];rng=random.Random(20261011);smooth=0.0
 for i in range(n):
  t=i/rate;u=i/max(1,n-1)
  if kind=="pop":value=(math.sin(2*math.pi*(760-260*u)*t)+.35*math.sin(2*math.pi*1180*t))*math.sin(math.pi*u)**1.6*.14
  elif kind=="click":value=(rng.random()*2-1)*math.exp(-u*9)*.11
  elif kind=="whoosh":
   smooth=.86*smooth+.14*(rng.random()*2-1);value=smooth*math.sin(math.pi*u)**1.5*.11
  else:value=(math.sin(2*math.pi*660*t)+.42*math.sin(2*math.pi*990*t))*math.exp(-u*4.5)*.10
  out.append(value)
 return out


def _write_sparse_wav(path,sounds,rate=48000):
 total=max([rate//10]+[start+len(samples) for start,samples in sounds]);data_bytes=total*2
 with open(path,"wb") as f:
  f.write(struct.pack("<4sI4s4sIHHIIHH4sI",b"RIFF",36+data_bytes,b"WAVE",b"fmt ",16,1,1,rate,rate*2,2,16,b"data",data_bytes))
  f.seek(44+data_bytes-1);f.write(b"\0")
 with open(path,"r+b") as f:
  for start,samples in sounds:
   f.seek(44+start*2);raw=f.read(len(samples)*2);old=struct.unpack("<"+"h"*len(samples),raw)
   mixed=[max(-32767,min(32767,a+round(b*32767))) for a,b in zip(old,samples)]
   f.seek(44+start*2);f.write(struct.pack("<"+"h"*len(mixed),*mixed))


def render_sfx(project,resolved,intro,speed):
 project=Path(project);(project/"work").mkdir(parents=True,exist_ok=True);sounds=[];rate=48000
 for event in resolved["events"]:
  if not event["enabled"] or event["sfx"]=="none":continue
  start=round((event["start"]/speed+intro)*rate);sounds.append((start,_tone(event["sfx"],rate)))
 path=project/"work/motion-sfx.wav"
 if sounds:_write_sparse_wav(path,sounds,rate)
 else:path.unlink(missing_ok=True)
 return path if sounds else None,len(sounds)


def build_stickers(project,resolved,width,height,intro,font_manifest):
 """Resolve each sticker source and pre-render an alpha clip; returns overlay instructions."""
 import stickers
 project=Path(project);c=s2v.settings(project);speed=c["speed"];fps=c["fps"];clips=[];credits=set()
 folder=project/"work/stickers";folder.mkdir(parents=True,exist_ok=True)
 for e in resolved["events"]:
  if e["type"]!="sticker" or not e["enabled"]:continue
  path,credit=stickers.resolve(e["source"],project)
  if credit:credits.add(credit)
  start=e["start"]/speed+intro;end=e["end"]/speed+intro;seconds=end-start;size_px=round(e["size"]*height)
  key=stickers.clip_key(e["source"]+str(path.stat().st_mtime_ns),e.get("caption"),seconds,fps,size_px,e["tilt"])
  out=folder/f"{e['id']}-{key}.mov"
  if not out.exists():
   canvas=stickers.build_clip(path,out,seconds,fps,size_px,e["tilt"],e.get("caption"),font_manifest["zh"]["file"])
  else:
   canvas=int(next(x for x in s2v.probe(out)["streams"] if x["codec_type"]=="video")["width"])
  cx,cy=STICKER_ANCHORS[e["anchor"]]
  clips.append({"id":e["id"],"path":str(out),"start":round(start,3),"end":round(end,3),"x":max(0,round(cx*width-canvas/2)),"y":max(0,round(cy*height-canvas/2))})
 for old in folder.glob("*.mov"):
  if str(old) not in {x["path"] for x in clips}:old.unlink()
 cred=project/"output/credits.txt"
 if credits:cred.parent.mkdir(exist_ok=True);cred.write_text("贴纸素材署名 / Sticker credits\n"+"\n".join(sorted(credits))+"\n",encoding="utf-8")
 else:cred.unlink(missing_ok=True)
 return clips


def prepare(project,width,height,band,intro,font_manifest):
 project=Path(project);c=s2v.settings(project);resolved=validate_plan(project,True)
 if not c["motion_enabled"]:
  (project/"work/motion.ass").unlink(missing_ok=True);(project/"work/motion-sfx.wav").unlink(missing_ok=True)
  return {"events":0,"visual_events":0,"sfx_events":0,"ass":None,"sfx":None,"warnings":resolved["warnings"]}
 enabled=[e for e in resolved["events"] if e["enabled"] and (e["type"]!="word_highlight" or c["word_highlight"])]
 if not enabled:
  (project/"work/motion.ass").unlink(missing_ok=True);(project/"work/motion-sfx.wav").unlink(missing_ok=True)
  return {"events":0,"visual_events":0,"sfx_events":0,"ass":None,"sfx":None,"warnings":resolved["warnings"]}
 ass,visual=render_ass(project,resolved,width,height,band,intro,font_manifest)
 sticker_clips=build_stickers(project,resolved,width,height,intro,font_manifest)
 if c["sfx_enabled"]:sfx,count=render_sfx(project,resolved,intro,c["speed"])
 else:
  (project/"work/motion-sfx.wav").unlink(missing_ok=True);sfx,count=None,0
 return {"events":len(enabled),"visual_events":visual+len(sticker_clips),"sfx_events":count,"ass":ass,"sfx":sfx,"stickers":sticker_clips,"warnings":resolved["warnings"]}


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("project",type=Path);args=ap.parse_args()
 try:
  result=validate_plan(args.project,True);s2v.status(args.project,"motion","done",f"{sum(e['enabled'] for e in result['events'])} 个语义动效 · {len(result['warnings'])} 条提示")
  print(json.dumps(result,ensure_ascii=False,indent=2));return 0
 except Exception as exc:
  if (args.project/"project.json").exists():s2v.status(args.project,"motion","failed",str(exc)[:500])
  print(str(exc),file=__import__("sys").stderr);return 1


if __name__=="__main__":raise SystemExit(main())
