# 开源视频剪辑能力调研与整合（2026-10-13）

目标：让 screen2video 处理“已有录屏 + 讲述”时更快、更准、更好听。方法：GitHub API 取星数/最近推送/许可证（数据日期 2026-10-13），网页搜索补 2026 年新项目；只学习机制，不复制代码，不执行候选项目代码。星数衡量热度，不是质量评分。

## 候选与结论

| 项目 | Stars | 许可 | 学到的机制 | 结论 |
|---|---:|---|---|---|
| [microsoft/OmniParser](https://github.com/microsoft/OmniParser) | 25.5k | CC-BY-4.0 | 从像素解析 UI 元素再定位目标 | **adapt**：用 Apple Vision OCR（[ocrmac](https://github.com/straussmaximilian/ocrmac), MIT）定位按钮文字 → `visual.py find` |
| [Recordly](https://www.abduzeedo.com/recordly-free-open-source-screen-recorder-auto-zoom) / [jkuri/reframed](https://github.com/jkuri/reframed) / [siddharthvaddem/openscreen](https://github.com/siddharthvaddem/openscreen) (39.9k, MIT) / [CapSoftware/Cap](https://github.com/CapSoftware/Cap) | — | 多种 | 录制时按光标/点击自动缩放平移 | **adapt（反向）**：我们拿到的是已缩放成片、没有光标元数据，所以改为事后检测镜头运动（ORB + 相似变换），给出稳定窗口并拒绝会漂移的固定 callout |
| [Breakthrough/PySceneDetect](https://github.com/Breakthrough/PySceneDetect) | 5.2k | BSD-3 | 帧差检测切换 | **adapt**：只需“镜头是否在动”，用 OpenCV 帧间变换实现，未引入 PySceneDetect 依赖 |
| [jianfch/stable-ts](https://github.com/jianfch/stable-ts) | 2.3k | MIT | 识别后修正/稳定词时间 | **adapt**：异常词时间检测 + 窗口重识别（`asr.py recheck`），不引入新模型 |
| [m-bain/whisperX](https://github.com/m-bain/whisperX) | 24.5k | BSD-2 | wav2vec2 强制对齐得到精确词时间 | **defer**：效果最好但依赖 PyTorch + 中文对齐模型；本次先用零依赖的重识别方案，若高亮仍不同步再接入 |
| [xiph/rnnoise](https://github.com/xiph/rnnoise) / FFmpeg `afftdn`、`arnndn` | 5.9k | BSD-3 | 轻量语音降噪 | **keep**：`--denoise-engine ffmpeg` 用 FFmpeg 内置 afftdn，任何系统可用；arnndn 需另下模型，暂不默认 |
| [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | 4.8k | 未声明 | 深度降噪 | **reject**：2024 后未更新、许可不清 |
| [FluidSynth](https://github.com/FluidSynth/fluidsynth) (LGPL-2.1) + [pretty-midi](https://github.com/craffel/pretty-midi) (MIT) | 2.5k / 1.0k | — | 乐谱 → MIDI → SoundFont 真实乐器渲染 | **adapt**：`music_synth.py` 拆成 `score()` + 渲染器，自写最小 MIDI writer（不依赖 pretty-midi），检测到 fluidsynth + 音色库时用真实音色。只调用外部可执行文件，不链接 LGPL 代码 |
| [Tonejs/Tone.js](https://github.com/Tonejs/Tone.js) / [strudel](https://github.com/tidalcycles/strudel) | 14.8k / 3.0k | MIT / AGPL | 浏览器代码作曲 | **reject**：需浏览器渲染；strudel 为 AGPL |
| [Huanshere/VideoLingo](https://github.com/Huanshere/VideoLingo) | 18.8k | Apache-2.0 | Netflix 级字幕切分、整段语境翻译、术语表 | **keep（已有）**：本 skill 已按整段语境翻译 + Netflix 时间规范；新增屏幕术语表补齐“术语一致性” |
| [jianchang512/pyvideotrans](https://github.com/jianchang512/pyvideotrans) | 19.4k | GPL-3.0 | 翻译配音全流程 | **reject**：GPL，且配音不在范围内 |
| [WyattBlue/auto-editor](https://github.com/WyattBlue/auto-editor) | 5.5k | Unlicense | 按音量阈值自动剪掉静音 | **defer**：默认原音完整保留；“压缩长停顿”需同步改动字幕/动效时间轴，作为后续可选项 |
| [linyqh/NarratoAI](https://github.com/linyqh/NarratoAI) / [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | 11.4k / 130k | MIT | LLM 解说 + 素材拼接 | **reject**：面向生成解说/素材片，不是录屏精修 |
| [remotion](https://github.com/remotion-dev/remotion) / [motion-canvas](https://github.com/motion-canvas/motion-canvas) / [hyperframes](https://github.com/heygen-com/hyperframes) | 63.7k / 19.3k / 62k | 混合 | 代码驱动动效 | **keep（现状）**：ASS + FFmpeg 已覆盖需要的动效，避免浏览器渲染依赖 |
| [csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) / [ffmpeg-normalize](https://github.com/slhck/ffmpeg-normalize) | 0.8k / 1.5k | MIT / 未声明 | 两遍响度归一化 | **adapt**：借鉴“两遍 + 线性”思路，修复 loudnorm 静默回退 dynamic 的问题（固定增益 + 限幅） |

## 本次整合（v0.13.0）

1. `scripts/visual.py`：采样帧 → 镜头运动/稳定窗口 → Apple Vision OCR → 屏幕词表；`find` 判断 callout 能否用固定框。实测本片 `camera: dynamic`（30% 时间在动），Edge TTS 按钮 2 秒内漂移 17% 画宽 → 正确判为 `moving-use-keyword`；词表命中 Kokoro、MeloTTS、Edge TTS、Qwen TTS、豆包语音、硅基流动。
2. `asr.py`：自动并入屏幕词表；异常词时间自动重识别校时（实测纠正 101.6–111.3 → 110.26–111.32 秒）。
3. `local_audio.py --denoise-engine`：剪映 SAMI 不可用时用 FFmpeg afftdn（实测停顿底噪 -5.4 dB，讲话电平不变）。
4. `music_synth.py`：score/render 分离，支持 FluidSynth + SoundFont 真实音色与 `--midi` 导出；无音色库时行为与 v0.12 一致（相关系数 0.97）。

## 缺失证据

- FluidSynth 渲染尚未在本机运行：需用户同意安装 `fluid-synth` 并下载音色库。
- Whisper 提示词对术语只部分有效；WhisperX 强制对齐未实测。
- 所有听感结论需用户试听；Agent 只做了频谱与分段响度检查。
