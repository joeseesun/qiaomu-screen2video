# 安装与启动

技能路径取本 `SKILL.md` 所在目录。个人源码只放 `/Users/joe/Nutstore Files/.agents/skills/qiaomu-screen2video`；其他发现路径使用软链接。可移植安装不依赖这个绝对路径。

```bash
# 环境只建一次；默认字幕字体已随 skill 打包，其他可选字体按需缓存。
uv venv ~/.cache/qiaomu-screen2video/venv
uv pip install --python ~/.cache/qiaomu-screen2video/venv/bin/python 'fonttools[woff]' pillow numpy opencv-python-headless ocrmac
# 下文 $PY 指该环境 Python，$SKILL 指 skill 根目录，$JOB 指本次输出目录。
"$PY" "$SKILL/scripts/fonts.py"
# 配乐真实乐器音色（推荐，一次性）：FluidSynth + GeneralUser GS（32 MB，可商用）；缺失时自动退回纯代码合成。
brew install fluid-synth   # Linux: apt install fluidsynth
mkdir -p ~/.cache/qiaomu-screen2video/soundfonts && curl -fL -o ~/.cache/qiaomu-screen2video/soundfonts/GeneralUser-GS.sf2 \
  https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/684543d5e5efaef08d02be50dcda8d552478fa60/GeneralUser-GS.sf2
"$PY" "$SKILL/scripts/s2v.py" init "$VIDEO" --project "$JOB"
# 如需降噪或独立录音对齐，先执行下节的 local_audio.py，再开始 ASR。
"$PY" "$SKILL/scripts/visual.py" analyze "$JOB"   # 屏幕词表与镜头运动，供 ASR、字幕和 callout 使用
"$PY" "$SKILL/scripts/asr.py" "$JOB" --engine auto --context '本次视频的产品名与术语'
```

系统 FFmpeg 必须带 libass；脚本优先检测 macOS 的 `ffmpeg-full`。依赖缺失只补所需依赖，不加载 qiaomu-cut 或安装整套视频框架。识别前按 [ASR](references/asr.md) 判断引擎与时间精度。
