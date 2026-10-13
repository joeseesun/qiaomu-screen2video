# 响度与舒适听感

调研日期：2026-10-11。

所有视频都在最终混音后检查响度。只测原始人声不够，因为加速、降噪、配乐、侧链和 AAC 编码都会改变成片听感与真峰值。

默认目标：综合响度 `-17 LUFS-I`，允许误差 ±1 LU；响度范围目标 `7 LU`；真峰值目标 `-1.5 dBTP`，验收上限 `-1 dBTP`。这是面向 YouTube/B 站产品录屏和口播教程的工程选择：位于 EBU 为无元数据流媒体给出的 -20 至 -16 LUFS 区间内，并留出有损编码峰值余量。它不是平台强制值。

流程固定为：原声测量 → 可选降噪/人声整理 → 配乐归一化与侧链闪避 → 原创轻音效低增益混入 → 最终混音归一化 → AAC 编码 → 再次测量成片。轻音效默认 `sfx_db: -6`，其原始波形也保留峰值余量；高频逐词高亮默认无声音，避免持续打断讲述。最终测量写入 `output/render.json`；综合响度偏低则整体提升，偏高则整体降低。超标时重新混音，不靠播放器音量掩盖。

`voice_lufs` 默认为空。只有原始讲述跨段落明显忽大忽小时才先把人声整理到约 -18 LUFS；最终总线仍以 -17 LUFS-I 验收。LRA 数字通过后仍要试听开头、正常讲话、最响处和结尾，检查底噪被抬高、压缩抽吸、齿音、音乐盖字和突兀淡出。数值检测不能替代听感复核。

依据：

- [EBU R128](https://tech.ebu.ch/publications/r128)：使用综合响度、响度范围和最大真峰值描述节目音频。
- [EBU R128 s2](https://tech.ebu.ch/docs/r/r128s2.pdf)：无元数据流媒体可采用 -20 至 -16 LUFS 的分发范围，并使用真峰值限制。
- [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770/)：节目响度与真峰值测量算法。
- [Apple Podcasts 音频要求](https://podcasters.apple.com/support/893-audio-requirements)：口播参考约 -16 LKFS、真峰值不高于 -1 dBFS。
- [YouTube 音质增强说明](https://support.google.com/youtube/answer/16619284)：平台可能提供稳定音量或人声增强，但并非所有视频都有，不能代替上传前混音。

## 不要让 loudnorm 变成压缩器

单遍 `loudnorm` 在“所需增益 + 原真峰值 > TP 上限”时会**静默回退为 dynamic 模式**，把无人声的音乐段、停顿和片尾抬到接近讲话响度，听起来就是“配乐太大”。`render` 现在先测 premaster：若线性增益会顶破真峰值，就改用固定增益 + `alimiter`（只削少数峰值），并在 `render.json.normalization` 记录 `linear-gain+limiter` 或 `loudnorm-linear`。验收时分段测：讲话段与纯音乐片尾的 mean volume 应相差约 8–10 dB；若接近，先查 normalization 类型，再动 `music_db`。
