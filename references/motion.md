# 录屏语义动效

动效服务于理解和注意力，不按固定间隔随机塞素材。先读完整转写、逐词时间和代表帧，再写 `motion-plan.json`；所有时间均指**原始录屏时间**，渲染器会统一执行 `原时间 / speed + 片头时长`。

## 选择规则

| 类型 | 什么时候使用 | 默认声音 |
|---|---|---|
| `word_highlight` | 数字、产品名、关键动作、结论中的重点词 | 无；高频字幕变化不反复发声 |
| `keyword` | 一句话中最值得记住的 1–6 个汉字或短产品名 | `pop` |
| `callout` | 讲述明确对应屏幕上的按钮、区域、结果或状态 | `click` |
| `chapter` | 主题或步骤真正切换 | `whoosh` |
| `sticker` | 情绪点：惊喜、自嘲、反转、成就（表情或梗图） | `pop` |

同一时刻只保留一个 `keyword/callout/chapter` 主视觉；逐词高亮可与指引同时出现。所有停留时间均按**最终成片时间轴**计算：`最终可见时长 = (end - start) / speed`。花字通常 0.8–1.6 秒，界面指引通常 1.2–3.5 秒；全屏章节卡至少 1.8 秒，按标题文字量建议 2.2–4.0 秒。章节卡入场约 0.18–0.24 秒、退场约 0.22–0.28 秒，中间必须留下完整静止阅读时间。短于 60 秒的成片默认最多 1 张全屏章节卡；其他结构提示改用花字或界面指引。不要按固定间隔机械加动效，只有语义转换、真实操作或需要定位注意力时才出现主视觉。

优先级：真实界面指引 > 重点词高亮 > 解释结构 > 装饰。没有明确作用时不加 GIF、Emoji 或花字。不要用网络表情包填空，也不要让动画遮住字幕、鼠标、输入框、代码、菜单和结果区域。

品牌样式固定使用：乔木黑 `#111513`、向阳朱 `#F05A3C`、暖白 `#F5F0E8`。动画进入约 140–220ms，轻微缩放回弹，退出干净；不使用持续抖动、重发光、彩虹色和随机转场。

## Schema

```json
{
  "schema": 1,
  "profile": "balanced",
  "events": [
    {
      "id": "m0001",
      "type": "word_highlight",
      "cue_id": "c0003",
      "text": "本地运行",
      "reason": "核心卖点"
    },
    {
      "id": "m0002",
      "type": "keyword",
      "start": 4.2,
      "end": 5.4,
      "text": "完全本地",
      "anchor": "top-left",
      "sfx": "pop",
      "reason": "强化结果"
    },
    {
      "id": "m0003",
      "type": "callout",
      "start": 8.0,
      "end": 10.0,
      "target": {"x": 0.68, "y": 0.26, "w": 0.19, "h": 0.13},
      "label": "点这里生成",
      "sfx": "click",
      "reason": "讲述对应实际按钮"
    },
    {
      "id": "m0004",
      "type": "chapter",
      "start": 13.0,
      "end": 14.5,
      "title": "第二步 · 生成音乐",
      "subtitle": "Generate locally",
      "sfx": "whoosh",
      "reason": "话题从安装切到生成"
    }
  ]
}
```

- `word_highlight`：`text` 必须存在于对应 `captions.json` 中文中。优先省略 `start/end`，让脚本从 `transcript.raw.json.segments[].words[]` 解出真实词时间；ASR 没有词时间时才显式填写经过听核的 `start/end`，不能按字数均分冒充对齐。
- `keyword.anchor`：`top-left`、`top-center`、`top-right`、`middle-left`、`middle-right`。默认避开底部字幕区。
- `callout.target`：相对于**原视频画面**的 0–1 坐标 `{x,y,w,h}`，不包含新增字幕带。必须观察事件时刻附近的真实帧后填写。录屏若带自动缩放/平移（Screen Studio 类镜头运动），坐标会随镜头漂移：至少比对事件起止两帧，目标位移超过框宽 1/4 就不要用 callout，改用 keyword。优先用 `visual.py find "$JOB" --text "按钮文字" --start S --end E`：它从 OCR 中定位文字，返回 `callout: ok` 与可直接写入的 `target`，或 `moving-use-keyword`。`work/visual-analysis.json.stable_windows` 列出镜头静止区间，callout 和章节卡优先放在其中。脚本自动绘制聚光遮罩、向阳朱描边框、箭头和可选标签。
- `chapter`：覆盖在继续播放的原画面上，不延长时间轴。标题短、结果清楚，不重复整句字幕。`start/end` 仍写原素材时间，但校验器会按 `speed` 换算最终时长。低于 1.8 秒直接报错；低于按文字量计算的阅读时间会提示。若找不到足够时间，不要硬塞章节卡，改成 `keyword`，或把章节卡放到自然停顿处。
- `enabled` 默认为 `true`；`sfx` 可选 `none/pop/click/whoosh/chime`。声音由 Python 数学波形与确定性噪声原创合成，不打包外部采样。

运行验证：

```bash
"$PY" "$SKILL/scripts/s2v.py" motion "$JOB"
```

验证结果写入 `output/motion-qa.json`，HTML 展示每个事件、最终可见秒数、触发原因、声音和密度/安全区提示。提示不阻塞生成；格式错误、越界目标、缺失 cue、伪造词时间或章节卡短于 1.8 秒会阻止动效渲染。没有 `motion-plan.json` 时仍可输出基础字幕版，但不能声称语义动效已经完成。

## 实现与验收

核心实现继续使用 FFmpeg 与 libass，不新增浏览器渲染依赖：逐词高亮复用字幕的真实换行和坐标；花字、聚光框、箭头和章节卡使用第二层 ASS；声音生成一条稀疏 PCM 音轨，再以 `sfx_db` 混入最终响度流程。GIF 只可作为明确授权的输入素材；若以后接入 Lottie/Motion Canvas，应先渲染透明 PNG 序列或带 Alpha 的视频，再交给 FFmpeg 合成。

实际交付至少检查：每类动效的一帧、最长字幕、竖屏/横屏安全区、指引目标准确性、逐词同步，以及讲话密集处音效是否抢人声。数值验证不能代替看画面和听声音。

参考：[TikTok Creative Codes](https://ads.tiktok.com/business/library/TikTok_CreativeCodes_May2023.pdf)、[TikTok 视频广告指南](https://ads.tiktok.com/business/en/guides/video-advertising-guide)、[Aegisub ASS Override Tags](https://aegisub.org/docs/latest/ass_tags/)、[FFmpeg ASS](https://ffmpeg.org/ffmpeg-filters.html#ass)、[Motion Canvas](https://github.com/motion-canvas/motion-canvas)、[Lottie Web](https://github.com/airbnb/lottie-web)。

## 抖音式花字与贴纸（v0.15）

### 时机比样式重要

花字和贴纸是“重音”，必须踩在讲述的情绪点上，而不是均匀撒在时间轴上：

1. **踩词**：用 `cue_id` + `at_word` 代替手写 `start`。脚本从真实词时间取发音起点，提前约 60 ms（成片时间）出现——看起来“正好打在字上”；`hold` 设最终停留秒数（花字默认 1.3，贴纸 1.5）。不写 `at_word` 时才手填 `start/end`。
2. **选点**：只放在 hook 承诺、数字/结论、情绪转折（惊喜、吐槽、自嘲、反转）、成果出现的那一刻。教程讲解中途、正在操作界面时不放贴纸。
3. **密度**：花字 + 贴纸合计 ≤ 8 个/分钟；任意两个主视觉间隔 ≥ 1.5 秒；两张贴纸间隔 ≥ 6 秒（梗密了就不好笑）。超出由 `motion` 警告。
4. **位置**：贴纸默认右上，花字默认左上，都避开底部字幕区。运行过 `visual.py analyze` 时，校验器会用 OCR 检查是否盖住屏幕文字（>20% 重叠警告）；盖住的是正在讲的界面就换 anchor，盖住的是无关正文可以接受。
5. **声音**：贴纸与花字默认 `pop`，与出现帧同步；收束用 `chime`。不在密集讲话段连续发声。

### 花字样式（审美规则）

教训（2026-10-13 用户反馈“花字太丑”）：常规字重伪加粗 + 三层描边 + 上下双色填充 + 倾斜 + 重阴影 = 廉价感。改为先在真实帧上原型对比再定稿，规则如下：

1. **一种重字体**：花字统一用 Noto Sans SC **Black**（OFL，由 `flower_font()` 从缓存可变字体实例化），绝不对细字体 `\b1` 伪加粗。
2. **颜色 ≤ 2 + 墨色**：品牌向阳朱 + 白/暖白 + 乔木黑。只给 `emphasis` 指定的关键词换强调色，不做渐变、不做双色拆分填充。
3. **一层效果**：要么一个色块底，要么一层描边 + 硬投影，不叠加多层描边。
4. **克制动效**：入场 ≤ 240 ms，回弹幅度 ≤ 4%，旋转 ≤ 6°；退场 ≤ 170 ms 淡出。不从 0% 放大。
5. **整片一种风格**：在计划顶层写 `keyword_style`，不要逐个混用。
6. **宽度用 libass 口径测量**：libass 的 fs 对应 winAscent+winDescent，Noto Sans SC 实际字面约为 fs × 0.69；色块宽度按此计算，左右留白相等。

| `style` | 观感 | 适用 |
|---|---|---|
| `label`（默认） | 向阳朱圆角标签，白色粗黑体，柔和投影；色块自左展开、文字随后淡入 | 教程、产品讲解，“高级感” |
| `stroke` | 白色粗黑体 + 单层乔木黑描边 + 硬投影，`emphasis` 为向阳朱；92→104→100% 轻弹 | 抖音式情绪点、口播强调 |
| `card` | 暖白卡片 + 黑描边 + 向阳朱错位底块，黑字；上浮落定，6°→2° | 轻松、个人风格内容 |
| `brand` | 旧版斜角色块 | 兼容旧项目 |

改样式时先用真实帧原型（同一 ASS 渲染器）并排比较至少 3 个方向，再写进代码；原型脚本思路见 `reports/flower-text-research.md`。

### 贴纸 schema

```json
{"id":"m0004","type":"sticker","cue_id":"c0004","at_word":"免费","source":"noto:1f389",
 "anchor":"top-right","size":0.24,"hold":1.6,"tilt":-4,"sfx":"pop","reason":"情绪高点"}
```

| source | 内容 | 许可 / 处理 |
|---|---|---|
| `noto:<码点>` | Google Noto 动态表情 GIF（约 300 个会动的表情，512 px），如 `1f389` 🎉、`1f602` 😂、`1f525` 🔥、`1f62d` 😭、`1f44d` 👍 | CC BY 4.0：自动写入 `output/credits.txt`，发布时贴进简介 |
| `fluent:<名称>` | Microsoft Fluent 3D 表情 PNG，如 `fluent:Trophy` | MIT；原图 256 px，`size` 建议 ≤ 0.16，否则发虚 |
| `memegen:<模板id>` + `caption` | memegen.link 梗图模板（如 `fine`、`drake`、`buzz`），中文梗字由本地字体排版，不交给 API | 代码 MIT；模板图片版权由使用者判断（用户已确认可用于公开视频） |
| `file:<相对路径>` | 用户自己的 PNG/GIF/WebP 梗图 | 用户自负 |

贴纸先由 `stickers.py` 渲染为带 alpha 的 PNG-MOV（弹跳入场、轻微漂浮、缩小淡出，GIF 自动循环），再由 FFmpeg 叠加在画面之上、字幕之下，所以字幕永远可读。素材缓存在 `~/.cache/qiaomu-screen2video/stickers/`。

参考：[PyonFX](https://github.com/CoffeeStraw/PyonFX)（ASS 逐字特效思路）、[Remotion TikTok 字幕模板](https://github.com/remotion-dev/template-tiktok)、[Noto 动态表情](https://googlefonts.github.io/noto-emoji-animation/)、[Fluent Emoji](https://github.com/microsoft/fluentui-emoji)、[memegen](https://github.com/jacebrowning/memegen)。
