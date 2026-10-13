# Creation handoff

已创建 qiaomu-screen2video v0.1.0，轻量个人初版。主入口 SKILL.md，核心为三个 Python 脚本（ASR、字体、合成）和一张原生 HTML 页面；没有 qiaomu-cut 依赖。

本地安装、真实 ASR、FFmpeg 导出、字幕字体、HTML 播放已验证。可选外部服务的未验收项列在 verification.md。研究依据见 research.md。无远端发布；当前源目录是个人 Nutstore skills 唯一目录。


## v0.2.0 更新

加入可选本地剪映音频降噪、频域独立录音对齐，以及实际识别音频哈希、成片音轨选择和原音恢复。已验证优势是同一处理音轨贯穿 ASR/混音，旧字幕和旧缓存不会因只比较视频文件而误用；设计优势是失败不替换此前选择，版本哈希变化拒绝猜测 ABI。独立实验采用原始应用模型，未打包专有文件。维护方法参考 qiaomu-meta-skill；此次窄更新不做新候选 skill 搜索。验证与未验收项见 [本地音频记录](local-audio-verification.md)。
