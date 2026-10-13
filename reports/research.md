# 实现取舍与资料核对

日期：2026-10-11。目标为个人可用的轻量已有录屏后处理 skill，不做通用视频创作框架。

## 本地依据

- qiaomu-clipper：核对 native/asr_runner.py、asr_cloud.py、asr_engines.py。采用独立模型环境、16kHz PCM、标准字幕结果与云端状态校验。没有复制 Native Messaging 服务。
- qiaomu-cover-design：核对 src/fontmanifest.ts、scripts/build-font-library.py。选其开源字体家族 Noto Sans SC + Inter；字幕改用 700/600 字重，完整上游字体避免 UI 子集缺字。
- qiaomu-cut：仅参考已有封面方法的内容承诺、短标题、产品主体和小图可读性。不依赖其导演/镜头/多媒体服务编排。
- qiaomu-suno-master：可选音乐路线需要真实可用的 CLI/浏览器入口，不能凭空编造 Suno 私有 API。

## 先例检索

用 qiaomu-meta-skill 的 research_prior_art.py 查询 skills.sh、SkillsMP：screen recording subtitles ffmpeg / bilingual subtitle transcription，共去重 27 个 family。安装量只是发现线索，不当作质量证明。

- [SmartSub](https://github.com/buxuku/SmartSub)：借鉴识别、翻译和字幕输出分离；不复制 GUI 或大型依赖树。
- [VideoLingo](https://github.com/Huanshere/VideoLingo)：借鉴语义分句后对齐翻译；不接入配音、完整视频平台流水线。
- [demo-video-skill](https://github.com/kminer2053/demo-video-skill/blob/main/SKILL.md)：读了源文档，采用真实 FFmpeg 导出与抽帧验收；拒绝重新录制浏览器、假鼠标和多轮强制确认。
- media-use：发现为大型媒体编排器，本需求不采用，未把其能力宣传当作验收证据。
- openchatcut transcription：目录中发现，源码链接返回 404；未依赖。

## 双语字幕实现

采用 ASS 两种 Style、同一组时间码、上下分层。中文白字深描边，英文深字白描边；也提供双白字、底部独立字幕带。普通 SRT 不携带可靠字体/描边信息，因此另存 SRT 便于平台上传，成片用 ASS 烧录。

- [Aegisub Styles](https://aegisub.org/docs/latest/styles/)：字体、描边、颜色、对齐与边距。
- [FFmpeg ass](https://ffmpeg.org/ffmpeg-filters.html#ass)：libass 烧录及字体目录。
- [Netflix 简体中文规范](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215986007-Chinese-Simplified-Timed-Text-Style-Guide)：用其成人中文 9 字/秒作为阅读提示，非声称本视频符合 Netflix 交付标准。
- [FFmpeg sidechaincompress](https://ffmpeg.org/ffmpeg-filters.html#sidechaincompress)：讲话作为侧链，降低音乐；不删原声口头词。

## ASR 与封面

- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)：官方 ForcedAligner 是额外模型；轻量 MLX 路线不能假称逐词对齐。
- [Whisper](https://github.com/openai/whisper)：turbo 用于原语转写，英文由 Agent 另译。
- [豆包录音极速版](https://docs.volcengine.com/docs/DoubaoVoice/recording-file-recognition-lite-http?lang=zh)：使用公开 recognize/flash 合约与 utterance 毫秒时间。
- [YouTube 缩略图帮助](https://support.google.com/youtube/answer/72431)：本次页面推荐 16:9、3840×2160。小尺寸生成图不得冒充原生 4K；按实际模型能力交付并单独说明。B 站兼容横版主体/标题安全区，具体上传规格以发布时验证为准。

HTML 使用原生 CSS/JS、本地数据快照、相对媒体链接。决策文件只包含允许的样式与混音键；不运行命令，不做强制审批门。

## 语义动效

- TikTok Creative Codes 与官方视频指南把文字、动作、转场和声音列为维持注意力的组合，同时强调开头钩子、移动端安全区及声音与画面的同步。本 skill 将其收窄为录屏需要的重点词、真实界面指引、章节切换和少量声音，不照搬广告节奏。
- [Motion Canvas](https://github.com/motion-canvas/motion-canvas) 和 [Lottie Web](https://github.com/airbnb/lottie-web) 可作为以后扩展透明矢量动画的参考；当前实现继续使用 FFmpeg/libass，减少 Node/浏览器依赖。
- [OpenCut](https://github.com/floomhq/opencut) 的声明式时间线、逐词字幕和关键词覆盖层提供了架构参考；当前 skill 不引入其 Remotion 依赖。
- GIF 不作为默认交付格式。当前箭头、聚光框、花字和章节卡全部由 ASS 矢量/文字生成；`pop/click/whoosh/chime` 为本地数学波形，不抓取网络音效。

## 剪辑节奏与认知负荷补充

- YouTube 官方将留存曲线中的平段、峰值与下坠作为复盘依据，并建议把后段的高留存内容提前；因此不把固定“每 N 秒一个动效”当作目标，先确保开头兑现封面承诺，再根据真实留存迭代。
- TikTok Creative Codes 使用 hook–body–close 结构，并把文字、动作、转场和声音视为有目的的注意力刺激；本 skill 只在语义转换、真实操作和结果出现时使用，不连续堆叠。
- Walter Murch 的剪辑优先级将情绪、故事和节奏放在空间连续性之前；对应录屏教程时，先判断观众的期待、操作链和理解节奏，再决定是否加动效。
- 多媒体学习研究支持删去无关内容、用信号提示关键区域、在有意义的边界分段。聚光框属于任务相关信号；装饰 GIF、重复文字和过密章节卡会增加额外处理负担。
- Netflix 字幕时间规范要求避免闪现，较长文字尽量延长屏幕时间并完整回看；英文成人内容 17 字符/秒被用作章节卡阅读时间的保守基线。章节卡同时加入 0.8 秒定位与动画余量，最终建议 2.2–4.0 秒。
- 2026-10-11 的真实失败样例显示，原素材 1.3–1.5 秒的章节卡经 1.35 倍速后只剩约 0.96–1.11 秒，入退场后无法阅读。v0.10.0 开始按最终时间轴校验，低于 1.8 秒直接拒绝渲染；短于 60 秒默认只保留一张全屏章节卡。
