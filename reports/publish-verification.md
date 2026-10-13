# v0.16.0 发布前验证

日期：2026-10-13。目标仓库：joeseesun/qiaomu-screen2video。

- 使用既有运行 venv 执行 `python -m unittest discover -s tests -v`：40/40 通过，无跳过，包含音乐 NumPy/FluidSynth 两条渲染路径与本地贴纸合成。
- 系统 Python 缺少 NumPy / Pillow，首次检查未完整运行；切换到准备好的 skill venv 后全部通过。README 明确使用该 venv。
- `python tests/smoke_render.py`：12 项真实 FFmpeg 集成检查通过，包括字幕带、逐词高亮、花字、界面指引、章节卡、轻音效、配乐侧链与无侧链、中文空格路径、完整解码、缓存复用及设置改变后的重渲染。
- README 的 `docs/assets/render-example.png` 来自上述实际导出，在成片 0.75 秒抽帧。画面和音调都是合成测试素材，不能用于宣称真实识别准确率或人声音质。
- 新增隔离安装回归检查：没有相邻 qiaomu-profile skill 时仍可读取随包头像与公众号二维码。旧实现复现 FileNotFoundError，修复后通过；片尾优先使用包内资产。
- 字体安装脚本已真实执行：中文缓存元数据为 IPA，英文为 OFL-1.1，字体 SHA-256 未变化。中文许可正文及上游中文译文随包保留；来源为上游 v1.305 标签与字体 name 表。
- 默认字体及各自 IPA / OFL 许可证保留；MIT LICENSE 保留；专有剪映库、模型、环境及缓存不进入分发包。
- README 已补安装步骤、依赖检查、自然语言示例、故障排查、上游致谢与服务限制；音乐说明以当前代码原创默认值为准。

## 验证范围

本次验证覆盖包与渲染机制；未重新调用云 ASR、生图、YuE2、Suno，未重跑剪映原生音频推理或完整 Windows 流程。历史验证见 verification.md。人工完整播放与听审仍按每个真实视频执行，本次测试不将 audio_review / visual_review 改为 passed。

首次公开推送后，qiaomu-skill-publisher 已完成 npx skills 发现与临时目录真实安装验证。生成的 review.html 中 JavaScript 通过 node --check；包内 Markdown 文件链接已核对。最终发布身份以 GitHub main 和远端文件核对为准。
