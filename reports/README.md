# 报告交付目录

本目录根路径下的短中文文件名为最终可交付文件，优先使用这些文件。

| 文件 | 用途 |
| --- | --- |
| `项目报告.docx` | 完整 Word 项目报告，包含项目背景、技术路线、推理后端、线程通信、训练结果、部署和展望。 |
| `路演PPT.pptx` | 风格 B 白底理性竞赛风路演 PPT，封面页和章节标题页由 image2 生成。 |
| `竖版海报.png` | 9:16 竖版项目海报，文字由 image2 直接生成。 |
| `横版海报.png` | 16:9 横版项目海报，文字由 image2 直接生成。 |

## 子目录说明

| 目录 | 内容 |
| --- | --- |
| `assets/` | Word 报告和 PPT 使用的架构图、训练曲线、样例图等可视化资产。 |
| `posters/` | 海报生成过程文件和原始 image2 输出文件。 |
| `roadshow_ppt/` | PPT 框架、风格候选、image2 章节页和 PPT 过程素材。 |

## 重新生成

```powershell
D:\miniconda3\envs\garage_ocr\python.exe scripts\generate_project_report.py
D:\miniconda3\envs\garage_ocr\python.exe scripts\generate_roadshow_ppt.py
```

说明：海报最终版采用 image2 直接生成文字的版本，当前根目录的 `竖版海报.png` 和 `横版海报.png` 为最终交付版。
