# ASR：文本正确与时间正确是两项检查

实现参照 Qiaomu Clipper 的 `native/asr_runner.py`、`asr_cloud.py`、`asr_engines.py`，2026-10-11 核对。只复用设计：独立 Python 环境、16kHz mono PCM、标准句级结果、缓存、有限重试、云端业务状态检查。新包没有复制 helper，也不读浏览器 cookie/插件中的密钥。

| 引擎 | 本 skill 用法 | 时间精度与限制 |
|---|---|---|
| 豆包录音极速版 | 已有凭据时 auto 优先；中文录屏推荐 | 读取 utterances 的毫秒时间，不用全文平均分配 |
| mlx-whisper | Apple Silicon 本地首选 | 原语识别 + word_timestamps，英文翻译单独由 Agent 做 |
| faster-whisper | CPU 跨平台后备 | int8 + VAD；读已准备好的 PCM，避开不必要的 PyAV 解码耦合 |
| mlx-qwen3-asr | 复用 Clipper 已安装环境 | 以停顿分块；标记 `pause-chunk-estimated`。不是逐词对齐，长句需重分段/检查 |
| Qwen + ForcedAligner | `--engine qwen-aligned --python ...`，单独可选环境 | 官方 Qwen3-ASR + Qwen3-ForcedAligner；额外依赖/模型，不默认安装。首次 provider 运行仍需验证 |

`auto` 顺序：配置的豆包 → 已安装 MLX Whisper → 已安装 faster-whisper → 已安装 MLX Qwen。无凭据不会擅自找别人的云接口；显式 engine 不静默切换。首次使用本地模型可能下载较大权重，告诉用户实际状态。

```bash
# 云端（凭据由运行环境提供，不写入项目或 skill）：
export DOUBAO_ASR_API_KEY='...'
# 或 DOUBAO_ASR_APP_KEY + DOUBAO_ASR_ACCESS_KEY
# 可选 DOUBAO_ASR_ENDPOINT（HTTPS）、DOUBAO_ASR_RESOURCE_ID
# 默认 endpoint: https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash
# 默认 resource: volc.bigasr.auc_turbo

# 本地独立环境：任选一种，不要全部安装。
uv venv ~/.cache/qiaomu-screen2video/whisper
uv pip install --python ~/.cache/qiaomu-screen2video/whisper/bin/python mlx-whisper
python3 scripts/asr.py "$JOB" --engine mlx-whisper --python ~/.cache/qiaomu-screen2video/whisper/bin/python
# 非 Apple 电脑把包/engine 换成 faster-whisper。

# 更重的 Qwen 官方带对齐路线，可选而非主链要求：
uv venv ~/.cache/qiaomu-screen2video/qwen-aligned --python 3.12
uv pip install --python ~/.cache/qiaomu-screen2video/qwen-aligned/bin/python qwen-asr
python3 scripts/asr.py "$JOB" --engine qwen-aligned --python ~/.cache/qiaomu-screen2video/qwen-aligned/bin/python
```

模型隔离：默认查找 `QIAOMU_TOOLS_HOME` 或 `~/.local/share/qiaomu-clipper/tools/{mlx,mlx-qwen3,faster-whisper}/bin/python`。只调用现有环境，不修改 Clipper。可显式 `--python`/`SCREEN2VIDEO_ASR_PYTHON`。Windows 请显式提供环境 Python。

术语通过 `--context` 提供给本地 Whisper/Qwen；豆包此版不注入私有 corpus 格式。数字、产品名和中英夹杂必须与录屏/语境核对，不能仅凭读音瞎改。云端 429/5xx 最多重试两次；鉴权、额度、未知超时不循环重放。

证据边界：本包会单独列出真实运行过的引擎；实现存在并不等于所有云账号、模型或硬件都通过测试。

来源：
- [火山引擎极速版](https://docs.volcengine.com/docs/DoubaoVoice/recording-file-recognition-lite-http?lang=zh)
- [Qwen3-ASR 与 ForcedAligner 官方用法](https://github.com/QwenLM/Qwen3-ASR)
- [Whisper 官方说明](https://github.com/openai/whisper)：turbo 不用于翻译任务。
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)

## 录屏里播放 TTS / 示例音频时

被演示的合成语音也会被识别并混进讲述句，且 Whisper 在其边界的词时间常被拉长（某个字跨数秒）。处理：发现单字时长 > 1 秒或句子跨越明显播放段时，对该区间 `ffmpeg -ss … -t 12` 截片单独重识别核对时间；示例朗读内容用「」标明或留空，不当作讲述。

## 屏幕词表与自动校时（v0.13）

- `visual.py analyze` 生成 `vocabulary.terms`（拉丁产品/模型名）与 `labels`（短中文界面标签）。`asr.py` 默认把它们追加到 `--context`（`--no-screen-context` 关闭）。实测 Whisper 的 initial_prompt 只能部分纠正（Kokoro 仍识别成 Kukuro），所以字幕清理时必须再对照词表人工校正。
- 本地引擎识别后自动检查“1–2 字的词持续 >1.2 秒”的句子，在其前后各 1.5 秒窗口用同一引擎重识别，取文本相似度最高的连续片段更新 start/end/words（文本不变），结果写 `work/asr-recheck.json`；`--no-recheck` 关闭。实测把 101.6–111.3 秒的错误时间校正为 110.26–111.32 秒。豆包按服务端句级时间，不做此检查。
