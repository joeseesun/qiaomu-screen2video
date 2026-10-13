# 从语音内容到封面与配乐

先读转写和录屏代表帧，再填 `brief.json`；不让文件名替代内容理解。

```json
{
  "promise": "一句话，让 AI 为 iOS 阅读应用给出四套设计方向",
  "evidence": [{"id":"c0004","quote":"生成了四个版本"}],
  "title": "一句话，4套设计",
  "cover_prompts": {
    "intro": "目标画布2404×1886，比例1.275:1，全画幅无边框；为片头生成背景素材，不在图中生成文字。主体和留白按最终标题位置构图，四周必须延伸到画布边缘。",
    "landscape": "目标画布3840×2160，16:9 YouTube/B站横版缩略图，全画幅无边框；移动端缩小后仍有一个主焦点，右下角避开时长覆盖区。",
    "vertical": "目标画布2160×3840，9:16 竖屏封面，重新构图而非裁切横版；标题与主体放在中部安全区，避开顶部和底部平台控件。"
  },
  "music_profile": "tutorial_focused",
  "music_prompt": "Instrumental upbeat focused electronic tutorial bed, 104 BPM, light tight percussion, soft synth pulses, sparse warm plucks, short simple motif, restrained forward motion, background for a Chinese software walkthrough, no vocals, no vocal chops, no dramatic risers, no dense lead melody",
  "music_exclude": "vocals, singing, rap, dramatic drops, aggressive drums"
}
```

## 封面

从“结果先行 / 前后对比 / 大数字 / 产品主体”中选一个。文字一般4–10个汉字或2–5个英文词、一个强调色，不硬造人脸、不堆截图小字、不承诺内容里没有的结果。标题与实际内容相符比“爆款”修辞更重要；不能承诺点击率。遵循 YouTube 官方建议：规则三分构图、易读字体、避免复杂堆叠，并在不同设备的小缩略图下检查。

优先 Codex 内置 `imagegen`（跟随当前工具/技能契约），备选用户已配置图片 API。只生成素材，不控制视频平台。需要准确 UI 时提供已观察过的录屏截图作参考；生成式概念画面标明概念，不冒充应用真实截图。默认让生图模型生成**无文字背景素材**，再用确定性排版叠加准确标题，避免中文错字。返回本地图片后用 `s2v.py asset` 登记；导入时会生成与源视频像素尺寸完全一致的 `cover.png`，渲染时使用铺满裁切，禁止上下或左右黑边。API 返回任务 ID 仍为 running，不算有封面。

默认一次任务产出三份封面，按用途分别设计，不能用一张图机械补边：

- **片头封面**：读取 `project.json.media.width/height`，目标像素与源视频完全一致；例如本片是 2404×1886，而不是16:9。模型输出尺寸不精确时，先要求相同比例与全画幅构图，再由确定性图像处理做 `cover` 裁切和高质量缩放。
- **YouTube/B站横版缩略图**：单独生成16:9；YouTube 当前官方建议3840×2160。标题、数字和主产品放在中央约80%宽×74%高，右下角约18%宽×20%高避免关键信息，防止时长标签遮挡。
- **竖屏/Shorts封面**：单独生成9:16（YouTube当前建议2160×3840），重新安排标题与主体，不从横版强裁。核心信息放在中央约72%宽×64%高，预留顶部和底部平台控件区域。

每个 prompt 都要写明：`full bleed to every edge; no letterbox, no black bars, no decorative frame, no watermark`。先在320×180（横版）和180×320（竖版）缩略预览检查，再看原尺寸。生成模型的原始图不足目标分辨率时，可为交付尺寸做高质量缩放，但不得假称原生4K。

建议的 Codex 生图 prompt 骨架：

```text
Use case: ads-marketing
Asset type: video cover background for <intro | 16:9 thumbnail | 9:16 vertical cover>
Primary request: based only on the transcript evidence, visualize <one concrete result>
Target canvas: <exact pixels>, aspect ratio <ratio>
Composition: one dominant focal point; reserve intentional negative space for the title; keep the title zone and product subject inside the stated safe area
Mobile crop safety: describe the central safe nucleus and the UI zones to avoid
Text: no text rendered in the image; title will be typeset afterward
Constraints: full bleed to every edge; no letterbox; no black bars; no border or frame; no watermark; no tiny UI text; no invented feature claims
```

来源：[YouTube 缩略图尺寸与比例](https://support.google.com/youtube/answer/72431)、[YouTube 缩略图与标题建议](https://support.google.com/youtube/answer/12340300)、[YouTube 视频比例与黑边说明](https://support.google.com/youtube/answer/6375112)。

默认片头0.7秒，原画面和两语言时间码同时后移；`intro_seconds:0` 只输出封面不插片头。视频比例不同时完整适配封面，不拉伸或裁掉文字。首帧可用不代表平台已自动采用缩略图。

生图背景建议不含文字，随后使用 `scripts/cover_compose.py` 进行全画幅适配与准确中文排版。标题必须用 `--kicker`（小标题）、`--line1`（主标题）、`--line2`（强调行）和 `--accent`（默认向阳朱可传 `#F05A3C`）按本片 `brief.json` 填写；不传时是脚本的示例文案，不能直接交付。片头、横版和竖版分别执行，不能把横版封面直接裁成竖版：

```bash
TITLE=(--kicker "产品 · 场景" --line1 "主标题" --line2 "强调行" --accent "#F05A3C")
"$PY" "$SKILL/scripts/cover_compose.py" intro-bg.png intro-cover.png --width "$VIDEO_W" --height "$VIDEO_H" --layout intro "${TITLE[@]}"
"$PY" "$SKILL/scripts/cover_compose.py" landscape-bg.png cover-16x9.png --width 3840 --height 2160 --layout landscape "${TITLE[@]}"
"$PY" "$SKILL/scripts/cover_compose.py" vertical-bg.png cover-9x16.png --width 2160 --height 3840 --layout vertical "${TITLE[@]}"
```

## 配乐方向

教程类配乐的核心是维持节奏和注意力，不能成为第二个叙述者。默认采用 `tutorial_focused`：96–112 BPM、明快但克制、轻打击乐、稀疏合成器或木质拨弦、短而容易忽略的循环动机。连续讲解越密，旋律越少、鼓点越软；界面操作和成果展示越快，节奏可提高，但仍避免大起大落。

可按内容切换：

| profile | 建议 | 适用内容 |
|---|---|---|
| `tutorial_focused`（默认） | 96–112 BPM，轻快电子、短动机、克制低频 | 软件教程、AI 工作流、录屏讲解 |
| `calm_explainer` | 82–98 BPM，温暖氛围、极少鼓点 | 概念解释、长段口播 |
| `fast_demo` | 110–124 BPM，干净律动、适量切分 | 快速成果展示、版本发布；减少连续讲话区使用 |
| `deep_build` | 90–105 BPM，极简脉冲、细微机械质感 | 编程、调试、产品搭建 |

不要默认使用“epic、intense、cinematic trailer、festival EDM”等描述。强瞬态会与辅音和点击声竞争，密集旋律会分散语言理解，过度起伏也会让自动 ducking 产生明显抽吸感。Adobe 的自动 ducking 指南建议根据讲话与音乐速度调整淡化速度；本 skill 继续使用人声驱动侧链和人工抽听，不把固定参数当成所有音乐都适用。

## 默认代码配乐；YuE2 / Suno 仅按需

默认直接用代码合成（2026-10-13 起，用户指定）：

```bash
"$PY" "$SKILL/scripts/music_synth.py" "$JOB/work/code-music/bed.wav" --seconds "$FINAL_SECONDS" --profile "$MUSIC_PROFILE"
"$PY" "$SKILL/scripts/s2v.py" asset "$JOB" music "$JOB/work/code-music/bed.wav" --provider code-synth
```

`--seconds` = 片头 + 源时长 / speed + 片尾。生成器先用 `score()` 写出编曲事件（同一份可另存 `--midi`），再由渲染器出声：默认 `--engine auto`——检测到 `fluidsynth` 与 `~/.cache/qiaomu-screen2video/soundfonts/*.sf2|sf3` 时用真实乐器音色（钢琴/暖 pad/原声贝斯/GM 鼓），否则用纯代码合成。音色库不随 skill 打包，按 SKILL.md 安装命令下载到缓存。

### 真实音色配乐（v0.14）

- 音色库：[GeneralUser GS v2.0.3](https://github.com/mrbumpy409/GeneralUser-GS)，32,319,396 字节，SHA-256 `9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe`（固定提交 `684543d`）。许可允许私人与商业音乐创作；样本来源作者无法 100% 追溯，若用于商业软件分发需自行评估，用于视频配乐即可。
- 声部映射（General MIDI）：伴奏/旋律=0 Acoustic Grand Piano，铺底=89 Warm Pad，低音=32 Acoustic Bass，打击=鼓通道 36 kick / 37 side stick / 70 maracas。FluidSynth 自带混响与合唱（`-R 1 -C 1`）。
- 同一份 `score()` 可 `--midi` 导出，用户可在 GarageBand/Logic 里换音色或改编后再登记为 music。
- 实测（2026-10-13，M5 Pro）：101 秒配乐 2.1 秒渲染完；波形无纯代码版的鼓点尖峰，频谱更平滑。听感需用户确认。
编曲使用手写 8 小节问答式旋律（只用和弦音与级进，强拍长音）、柔和分解和弦、pad 和轻打击；旋律 8 小节出现、8 小节休息，避免与讲述抢注意力。改旋律时逐音核对与和弦的协和关系（强拍避免悬挂四度/小九度）。Agent 不能试听时只报告频谱与分段响度，听感交给用户。

以下为用户明确要求时的模型路线，提供配乐时按以下顺序执行：

1. **YuE2 本地优先**：读取 `yue2-music`，进入其纯音乐工作流。文字生成默认让 YuE2 符号规划器作曲，自动 Vocal → Ins 后生成；不擅自使用 `--composer agent`。输出放在 `$JOB/work/yue2-music/`，保留 `planning/`、`conversion/`、实际 prompt 和可播放音频。先按 yue2-music 的当前说明检查本地模型与支持的设备（CUDA 或 Apple Silicon MPS），使用 --device auto；能力不足立即记录原因并回退，不反复下载或用低质量设置掩盖失败。
2. **Suno 回退**：YuE2 不可用或试听明显不合格时，按相同 prompt 走 Suno。读取 `qiaomu-suno-master` 的生成规则，不复制密钥、不调用隐藏接口、不在验证码失败时循环提交。
3. **代码原创配乐**：两者均失败，或用户明确要求“用代码生成配乐”时，运行 `scripts/music_synth.py`。它复用默认代码作曲路线，按 `music_profile` 写谱；检测到 FluidSynth 与音色库时使用乐器音色，否则用正弦分音与固定种子噪声合成。实际渲染引擎记录在结果 JSON 中，外部音色遵循其许可证，约数秒完成。音乐性有限，交付时如实标为“代码合成配乐”，不能说成 YuE2/Suno 作品；Agent 无法试听时只报告频谱/响度检查，听感交给用户。
4. **现有音乐或无配乐预览**：以上都不可用时可用用户提供的音乐；否则继续产出字幕预览版并明确标注缺少配乐。

YuE2 在 Apple Silicon 上较慢（实测见 yue2-music 的安装说明），可先用代码配乐渲染一版交付试听，YuE2 完成后重新 `asset ... music` 并 render，同时保留两版供用户选择。

YuE2 示例命令（路径由运行时发现的 `yue2-music` skill 根目录解析，禁止硬编码发现路径）：

```bash
"$YUE2/.venv/bin/python" "$YUE2/instrumental/scripts/instrumental.py" run \
  --style "$MUSIC_PROMPT" \
  --output "$JOB/work/yue2-music"
"$PY" "$SKILL/scripts/s2v.py" asset "$JOB" music \
  "$JOB/work/yue2-music/listen/listening.mp3" --provider yue2-music
```

若实际交付是 `listen/audio.flac`，登记该文件；不能假定输出扩展名。导入前用 ffprobe 验证音轨与时长，并试听讲话密集段、无讲话段和片尾。

## Suno 回退配乐

1. 用转写提炼情绪/节奏，不把字幕拿去唱；要求纯器乐、简单循环、稀疏编曲、无唱词/哼唱/人声切片。
2. 在当前环境发现 Suno 工具/CLI 后按其真实契约生成。若需现有个人路线，读取 `qiaomu-suno-master` 的生成部分；不要复制密钥、手写隐藏接口或在验证码/鉴权失败时循环提交。
3. 保存真实 clip ID / URL 和已下载音频，ffprobe 检查有音轨，再导入。此 skill 不假设存在官方 Suno 公共 API。
4. 没登录/额度不足/接口不可用时，保留 prompt 与 blocked 原因，先继续字幕版；用户给的本地音乐可替代。测试音不能标成 Suno 作品。
5. FFmpeg 对配乐单独做响度整理、低增益、半正弦曲线淡入淡出，再以选定讲述音轨作 sidechaincompress 控制信号（默认原声，可选对齐/降噪后音轨）。有片尾时音乐延续到片尾，最后 3 秒淡出到静音；讲述不因配乐被剪切。

默认配乐先标准化到约 -18 LUFS，再降低 17 dB（`music_db: -17`），并随人声继续压低；最终听感必须抽听，可通过 HTML 调整 `music_db`。不能把 dB 增益、LUFS 和峰值 dBFS 混为一个量。

当封面/配乐延迟时，先渲染字幕版，清晰标识缺少的资产；取得文件后重新登记并 render。已有 ASR/翻译不重跑。HTML 不成为审批队列。

来源：[YouTube 缩略图官方说明](https://support.google.com/youtube/answer/72431)、[Adobe 自动 Ducking](https://helpx.adobe.com/premiere/desktop/add-audio-effects/adjust-volume-and-levels/automatically-duck-audio.html)、[FFmpeg 音频滤镜](https://ffmpeg.org/ffmpeg-filters.html#sidechaincompress)、`yue2-music` 的纯音乐工作流、Qiaomu Cut 的封面原型与缩小检查方法（取其设计方法，不引入全套依赖）。
