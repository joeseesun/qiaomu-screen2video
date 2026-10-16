# 乔木 AI RSS 音频功能介绍：完整构建存档

这是 editorial-plate 样式第一次成片（v1→v12）的**原始构建脚本**，用来复现思路，不是开箱即用的流水线：

- `build.py`：剪辑区间（静音收紧）、变速（讲述 1.4×、产品朗读 1.0×）、ASS 事件、ffmpeg 滤镜图、配乐与响度混音。它里面的 ASS 片段已抽成可测试的 `scripts/editorial_ass.py`，新项目请用后者。
- `texts.py` / `texts_en.py`：56 条中英字幕（`读者提交` 已按界面文字纠正）。
- `render_plate4k.py`：4K 画板 + 点击涟漪，对应 `scripts/plate_render.py`。
- `run4k.sh`：4K 一键脚本。注意其中 `declare -A` 需要 bash（当时用 sh 运行，最后一步失败，手动补完）。

它依赖当时的工作文件（`t.json` 逐字转写、`proxy.mp4`、`plate4k.mp4`、`bed.wav` 配乐等），这些不在存档里。
