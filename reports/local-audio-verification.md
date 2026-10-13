# v0.2.0 本地音频接入验证

2026-10-11，在唯一个人源码目录更新。范围是可选音频降噪、频域独立录音对齐、ASR/渲染接入与恢复原音，未加入抠像、变速或视频算法。参考本会话既有 REA 探针，不进行新的 skill 目录研究：这是现有 skill 的窄功能更新。`qiaomu-meta-skill` 提供包与路由验证方法；前置降噪/对齐试验提供当前版本 ABI 与延迟依据。拒绝打包专有库/模型，也不以函数返回成功作为质量证据。

## 本轮实际运行

- `python3 -m unittest discover -s tests -v`：16/16，通过原有字幕/设置/云业务错误边界与新增音频篡改、路径越界、库哈希不符、处理失败保留音轨检查。
- `uv run --with pyyaml python <qiaomu-meta-skill>/scripts/validate_skill.py .`：通过。系统 Python 缺少 PyYAML 时该验证器会返回空 YAML 并产生误报；本轮用临时 uv 环境解析，未给 skill 的运行环境增加 PyYAML。已有本地包未宣称 npx 安装，保留 README install-command 提示。
- `trigger_eval.py`：14/14 启发式案例通过，含录屏降噪、外置录音对齐及剪映 UI/单独 WAV 的排除；不是独立模型触发评测。
- 原有 `tests/smoke_render.py`：真实 FFmpeg 配乐侧链、字幕带、无片头、中文空格路径、缓存复用、设置失效、无侧链导出共 7 项通过。
- 新增 `tests/smoke_local_audio.py`：真实 macOS Tingting 中文音频、固定随机底噪、原始剪映 SAMI 和 FFmpeg 路径，11 项检查通过；完整机器结果见 [JSON](local-audio-verification.json)。

SDK 给定 ±1375 ms 测试返回 ±1376 ms，适配器在附近 ±2 ms 内细调后得到 ±1375.0 ms；零偏移仍为 0。独立录音的实际裁切/补静音与参考波形相关性超过 0.98。静音不能冒充有效对齐，失败保留之前选定音轨。

降噪长度与视频时间轴一致，输出无无效/超限采样；对干净参考的相关性 0.998337 → 0.999317（本轮轻底噪样例，不替代前置 SI-SDR 实验）。旧转写被拒绝；模拟 provider 响应验证了 ASR 实际读取选定 16 kHz WAV 和缓存更新，不是豆包识别质量证明。

同时启用对齐、降噪、封面、配乐后真实导出 MP4，完整解码通过，扣除片头后的讲述与所选音轨相关性 0.995397。恢复原声后旧成片标记为过期。所有原生调用由 macOS 沙箱禁网，库/模型留在应用目录，编译缓存留在用户缓存目录。

## 尚未验证

- 本轮未人工听审，`audio_review` 仍为 pending；未改变 HTML 外观，不新增界面验收声明。
- 未使用真实豆包服务；ASR 改动验证的是输入选择和缓存，已有 Whisper/Qwen 的历史识别证据保留。
- 不外推到立体声保真、长录音时钟漂移、不同剪映版本、其他硬件或任意输入质量。对齐开头最多 60 秒，要求至少两秒共同讲述。
- 本地更新已通过现有 Codex 软链接生效；该 skill 目录没有 Git 仓库/远端，本轮没有发布声明。

## 复现

```bash
python3 scripts/local_audio.py --doctor
python3 -m unittest discover -s tests -v
~/.cache/qiaomu-screen2video/venv/bin/python tests/smoke_local_audio.py
```

真实样片与 WAV 留在 JSON 的 `fixture_path`；本包不携带样例音频、模型或二进制。
