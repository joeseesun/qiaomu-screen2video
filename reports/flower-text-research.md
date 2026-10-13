# 花字审美研究（2026-10-13）

触发：用户评价 v0.15 抖音式花字“太丑”。

## 问题诊断（v0.15 douyin 样式）
- 霞鹜新晰黑 Regular 加 `\b1` 伪加粗：笔画发糊、不够重。
- 三层描边（黑/朱/黑）+ 上白下金双色 clip 填充 + 4° 倾斜 + 半透明重阴影：元素过多，没有主次。
- 0→118% 弹跳过猛，像早期模板。

## 研究要点
- 层级：一个主元素，其他都退后；全部加粗等于没有重点（[Influencers Time](https://www.influencers-time.com/use-kinetic-typography-to-boost-short-form-video-retention/)）。
- 动效语气：punch/scale 表达确定，缓动滑入表达冷静；动效要少（同上）。
- 高级感：低饱和、纯色、少颜色（[数英](https://www.digitaling.com/articles/671873.html)）。
- 平台花字结构：字体色 + 最多 2–3 层描边是“上限”，不是默认（[阿里云花字配置](https://help.aliyun.com/zh/vod/developer-reference/word-art)）。
- 字幕/文字放置与配色：[OpusClip](https://www.opus.pro/blog/video-caption-design-placement)、[Animoto](https://animoto.com/blog/business/designer-approved-tips-text-social-videos)、[OpenClip 配色](https://openclip.app/guides/caption-color-guide.md)。
- 字体：思源/Noto Sans SC Black（OFL）、阿里巴巴普惠体 Heavy（免费商用）、得意黑（OFL）。

## 原型对比（同一真实帧、libass 渲染）
| 方案 | 结论 |
|---|---|
| label 朱色圆角标签 | 最干净，默认 |
| stroke 白字单描边硬投影 | 抖音式冲击，保留 |
| card 暖白卡 + 错位底块 | 有个性，保留 |
| 得意黑 + 下划线 | 白字压白界面对比不足，淘汰 |

首轮原型色块右侧留白过大：libass 字号口径与 Pillow 不同（fs ≈ winAscent+winDescent），校准系数 0.69 后修正。
