# 双语字幕：样式与实现

调研日期：2026-10-11。

采用 ASS 的两套 Style、相同 start/end、按每句实际行数计算两个底部锚点。FFmpeg 的 libass 烧录确定字体与描边；SRT 用于平台可切换字幕，不承担排版。英文先按完整语境翻译，再按 ID 对应中文，避免翻译改变时间轴。

## 固定默认组合与可切换组合

| `font_preset` | 字体与基准字号（1080 高） | 适用 |
|---|---|---|
| `signature`（固定默认） | 霞鹜新晰黑 Regular + Atkinson Hyperlegible Next SemiBold，56/38 | 清晰而有人文感，小屏字符区分度高，适合产品录屏与创作者内容 |
| `editorial` | 霞鹜文楷 Medium + Source Sans 3 SemiBold，建议 54/37 | 人文、知识讲解、阅读感较强 |
| `accessible` | Noto Sans SC Bold + Atkinson Hyperlegible Next SemiBold，建议 54/36 | 界面复杂、优先辨识度 |

默认锁定霞鹜新晰黑 Regular 与 Atkinson Hyperlegible Next SemiBold。霞鹜新晰黑用较清晰的黑体骨架保持屏幕辨识度，同时比通用 UI 黑体更有人文气质；依靠白字黑描边获得视频字幕需要的重量。Atkinson 以开放字腔和易混字符区分度提高英文小字可读性。两份上游字体及各自许可证（IPA / OFL）随 skill 打包，缓存清单记录 SHA-256、来源与字重。`editorial` 和 `accessible` 作为明确切换项，不自动猜测切换。

1080 高度基准：中文56、英文38；中文描边2.35、英文描边1.85；中文阴影1.2、黑色55%不透明，英文阴影0.8、黑色40%不透明；描边与阴影都按实际画面高度同比缩放。阴影只作向右下的轻分离层，不能替代描边，也不能做成发光或明显重影。英文基线位于画面底部约7.5%安全区，中文基线比英文上移“英文行高的 1.17 倍 + 0.4%画面高度”。默认不放大黑色底板；中文白字黑描边，英文黑字白描边。BBC 的字幕研究以单行约占播放器高度8%作为可读基准，本技能让英文达到中文约68%，避免把翻译缩成注释。参数仍须抽帧检查，不盲套16:9。

录屏教程默认 `speed: 1.35`。ASS 与 SRT 时间码按 `原时间 / speed + 片头时长` 变换；画面用 `setpts`、讲述用 `atempo` 同步处理。阅读速度检查以加速后的实际显示时长计算，不能只加速音画而保留旧字幕时间。

默认一行中文+一行英文；必要时每种最多两行。按字体真实宽度断行，保留英文词和产品名称，超宽报出具体 cue，请 Agent 压缩译文或按语义分句，不缩成小字。中文每秒9字和英文每秒20字符作为阅读提示；不为了满足提示擅自拉长字幕覆盖下一句。

逐词重点高亮不是另一套字幕排版：底层中文仍保持白字黑描边，`motion-plan.json` 只在真实词时间内叠加同位置的向阳朱词组。这样不会让所有字连续变色，也不会破坏双语行距。词时间缺失时必须听核后显式填写，不按字符数平均分配；详见 [语义动效](motion.md)。

保留原始文本、清理文本及差异。口头填充词在语义判断后删除；“先安装，然后启动”里的然后有逻辑意义，不能用全局 replace 删除。删除一个纯语气词单元时 zh/en 同时为空，音频仍不剪。

## 参考与取舍

- [Aegisub Styles](https://aegisub.org/docs/latest/styles/)：ASS 字体、描边、alignment 和 script-resolution margin 支持双语分层；不是把两语言拼到一个固定样式里。
- [BBC 字幕字号研究](https://bbc.github.io/gaad/how_big_should_subtitles_be/index.html)：单行字幕约占播放器高度8%，同时按设备和播放器尺寸验证。
- [Braille Institute Atkinson Hyperlegible](https://www.brailleinstitute.org/freefont/)：以字符区分度和低视力可读性为目标的免费字族。
- [霞鹜新晰黑 LXGW Neo XiHei](https://github.com/lxgw/LxgwNeoXiHei)：IPA Font License 1.0，当前打包上游 v1.305 Regular。
- [Atkinson Hyperlegible Next](https://github.com/google/fonts/tree/main/ofl/atkinsonhyperlegiblenext)：OFL-1.1，打包经上游可变字体实例化的 SemiBold 600 文件，名称与字重已固化。
- [霞鹜文楷](https://github.com/lxgw/LxgwWenKai) 与 [Source Sans](https://github.com/adobe-fonts/source-sans)：可切换的人文/编辑组合，均为 OFL-1.1。
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html#ass)：libass 渲染；必须实际检测滤镜。macOS 普通 ffmpeg 本机不带 ass，而 ffmpeg-full 带，不能只检查命令存在。
- [Netflix 简中指南](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215986007-Chinese-Simplified-Timed-Text-Style-Guide)：借鉴阅读速度和断句检查；录屏双语并非 Netflix 交付，不宣称完全合规。
- [SmartSub](https://github.com/buxuku/SmartSub)：ASR、翻译、双语与烧录分离；拒绝引入桌面端/配音/声纹系统。
- [VideoLingo](https://github.com/Huanshere/VideoLingo)：借鉴语义切分和对齐优先；不搬运全套 Streamlit/配音工作流，也不复制其 GPL 代码。

HTML 的 CSS 仅用于交互示意。最终可信排版证据来自 libass 抽帧；必须检查英文较长/中英混排的句子。
