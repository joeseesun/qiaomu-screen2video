#!/usr/bin/env python3
"""Install bundled defaults and download optional OFL subtitle font presets."""
import hashlib, io, json, os, shutil, urllib.request, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
CACHE=Path(os.environ.get('SCREEN2VIDEO_FONT_DIR',Path.home()/'.cache/qiaomu-screen2video/fonts'))
PRESETS={
 'signature':{
  'zh':{'filename':'LXGWNeoXiHei-Regular.ttf','bundled':'assets/fonts/LXGWNeoXiHei-Regular.ttf','bundled_license':'assets/fonts/LXGWNeoXiHei-IPA.md','license':'IPA','license_filename':'lxgw-neoxihei-IPA.txt','source_url':'https://github.com/lxgw/LxgwNeoXiHei/releases/tag/v1.305','folder':'lxgw-neoxihei','weight':400},
  'en':{'filename':'AtkinsonHyperlegibleNext-SemiBold.ttf','bundled':'assets/fonts/AtkinsonHyperlegibleNext-SemiBold.ttf','bundled_license':'assets/fonts/AtkinsonHyperlegibleNext-OFL.txt','source_url':'https://github.com/google/fonts/tree/main/ofl/atkinsonhyperlegiblenext','folder':'atkinsonhyperlegiblenext','weight':600}},
 'editorial':{
  'zh':{'filename':'LXGWWenKai-Medium.ttf','url':'https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Medium.ttf','license_url':'https://raw.githubusercontent.com/lxgw/LxgwWenKai/main/OFL.txt','folder':'lxgwwenkai','weight':500},
  'en':{'filename':'SourceSans3-SemiBold.ttf','url':'https://raw.githubusercontent.com/google/fonts/main/ofl/sourcesans3/SourceSans3%5Bwght%5D.ttf','axes':{'wght':600},'license_url':'https://raw.githubusercontent.com/google/fonts/main/ofl/sourcesans3/OFL.txt','folder':'sourcesans3','weight':600}},
 'accessible':{
  'zh':{'filename':'NotoSansSC-Bold.ttf','url':'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf','axes':{'wght':700},'license_url':'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt','folder':'notosanssc','weight':700},
  'en':{'filename':'AtkinsonHyperlegibleNext-SemiBold.ttf','url':'https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegiblenext/AtkinsonHyperlegibleNext%5Bwght%5D.ttf','axes':{'wght':600},'license_url':'https://raw.githubusercontent.com/google/fonts/main/ofl/atkinsonhyperlegiblenext/OFL.txt','folder':'atkinsonhyperlegiblenext','weight':600}},
}

def download(url,timeout=120):
 with urllib.request.urlopen(url,timeout=timeout) as r:return r.read()

def setup():
 from fontTools.ttLib import TTFont
 from fontTools.varLib.instancer import instantiateVariableFont
 CACHE.mkdir(parents=True,exist_ok=True);result={'default':'signature','presets':{}}
 for preset,pair in PRESETS.items():
  result['presets'][preset]={}
  for lang,spec in pair.items():
   dest=CACHE/spec['filename'];license_path=CACHE/spec.get('license_filename',spec['folder']+'-OFL.txt')
   if spec.get('bundled_license'):shutil.copy2(ROOT/spec['bundled_license'],license_path)
   elif not license_path.exists():license_path.write_bytes(download(spec['license_url'],60))
   if spec.get('bundled') or not dest.exists():
    payload=(ROOT/spec['bundled']).read_bytes() if spec.get('bundled') else download(spec['url'])
    if spec.get('member'):payload=zipfile.ZipFile(io.BytesIO(payload)).read(spec['member'])
    if spec.get('bundled') and not spec.get('axes'):
     tmp=Path(str(dest)+'.tmp');tmp.write_bytes(payload);os.replace(tmp,dest)
     font=TTFont(dest)
    else:
     raw=CACHE/(spec['folder']+'-source.ttf');raw.write_bytes(payload)
     font=TTFont(raw)
     if spec.get('axes'):font=instantiateVariableFont(font,spec['axes'],inplace=False,updateFontNames=True)
     font.save(str(dest)+'.tmp');os.replace(str(dest)+'.tmp',dest)
   font=TTFont(dest);family=font['name'].getDebugName(1)
   result['presets'][preset][lang]={'file':str(dest),'family':family,'weight':spec['weight'],'postscript':font['name'].getDebugName(6),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'source':spec.get('source_url',spec.get('url')),'bundled':bool(spec.get('bundled')),'license':spec.get('license','OFL-1.1'),'license_file':str(license_path)}
 (CACHE/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 return result
if __name__=='__main__':print(json.dumps(setup(),ensure_ascii=False,indent=2))
