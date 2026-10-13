# 本地讲述音频：降噪与对齐

先 `s2v.py init`，需要处理时运行 `local_audio.py`，再 ASR。仅清理字幕的任务继续原音默认流程。响度整理沿用 `voice_lufs` 和 FFmpeg；变速、抠像、补帧、视频降噪不在本次适配器内。

## 环境与边界

- Apple Silicon macOS、Xcode Command Line Tools、已安装 `/Applications/VideoFusion-macOS.app`。`python3 scripts/local_audio.py --doctor` 校验依赖和原始库/模型 SHA-256。
- 当前恢复的是剪映 11.5.0 的导出 C ABI，不是稳定公开 SDK。哈希不符会拒绝调用，升级后重新验证，不能跳过哈希检查。
- skill 只保存自行编写的调用源码，运行时读取本机应用目录。编译的探针保存在 `~/.cache/qiaomu-screen2video/native/<source-hash>/`，不复制库或模型到包内。
- 原生进程由 macOS `sandbox-exec` 禁止联网，不启动 UI、不读取账号或 Token。字体、ASR、图片和音乐的网络选择仍按各自流程。

## 降噪

`--denoise` 使用 SAMI identify 308、`unet_denoise_44k_music_model_v1.0.model`。FFmpeg 将所选讲述转换为 44.1 kHz 单声道 PCM16；SDK 默认强度，不能声称等于剪映界面的 0.85。探针以 512 个采样分块，补零排空，裁去已测得的 1024 采样延迟，保持视频时间轴与音频长度。输出存在无效采样或超限时失败。

处理音频会变成单声道讲述；不要对需要保留立体声空间、含原配乐或多音轨混合的素材默认开启。原视频、原音文件及旧处理结果均保留。降噪不能保证提高每段 ASR 的正确率，听核仍需做。

## 独立录音对齐

`--voice /path/to/recording.wav` 接受 FFmpeg 可解码的独立录音。录屏和独立录音必须含同一次讲述；无声录屏、另配的旁白不能使用自动音频对齐。

使用 identify 510、`time_align_freq_domain_v2.0.model`，检测两者开头最多 60 秒的 16 kHz 单声道音频；仅估计固定偏移。正偏移表示独立录音更晚开始播放，裁去其开头；负偏移在前方补静音。最终补齐/裁到视频长度。较短的独立录音末尾补静音，不拼回原声。

库结果以毫秒量化，调用成功后在其附近 ±2 ms 内按 16 kHz 采样细调，再算对齐音频的绝对相关系数。静音、有效重叠不足两秒或相关性低于 0.35 时拒绝替换音轨；阈值是本适配器的保守检查，不是 SDK 置信分数。原始返回值、细调偏移和检查结果均写入项目记录。长录音的时钟漂移、多段错位、开头一分钟没有共同声音、大量不同配乐不在验证范围内。

## 文件、缓存与恢复

每次调用写独立的 `work/audio-*/`，内含准备后的 WAV、降噪 WAV（如启用）、16 kHz ASR WAV、原生日志、偏移结果与 `processing.json`。全部成功后才更新 `project.json.audio_processing`；处理失败保留此前音轨。

ASR 缓存包含实际识别音频哈希。转写记录同一哈希；渲染检查当前音频和转写一致，阻止用旧时间码合成新讲述。输入处理 WAV 缺失/被改动也会阻止合成。恢复使用 `--reset`，不会删除历史产物，随后重新 ASR、清理翻译、渲染。

本次接入证据见 [验证记录](../reports/local-audio-verification.md)。前置独立实验完成于 2026-10-11：中文 WAV 降噪 SI-SDR 10.89 → 17.24 dB；频域 ±1375 ms 偏移返回 ±1376 ms。此数值是固定样例结果，不是所有输入质量保证。

## FFmpeg 降噪回退（v0.13）

`--denoise-engine auto|jianying|ffmpeg`。auto 先检测剪映 SAMI 适配器，不可用（非 Apple Silicon、版本/哈希不符）时改用 FFmpeg 内置 `highpass=70,afftdn(nr=12,nf=-42,tn=1)`，任何系统可用、无需下载模型。它对风扇/底噪等稳态噪声有效（实测停顿底噪 -59 → -65 dB，讲话电平不变），对键盘声、人声干扰等非稳态噪声弱于 SAMI。`processing.json.denoise.engine` 记录实际引擎，交付时如实说明。
