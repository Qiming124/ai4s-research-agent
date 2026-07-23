# =============================================================================
# server.export 包：课题工作笔记导出（Markdown / LaTeX / DOCX / PDF）。
# 非代写可投稿论文。
#
# 职责：
#     1. builder 从记忆层聚合 Markdown/LaTeX 源
#     2. docx_exporter / pdf_exporter 生成二进制
#     3. pandoc、reportlab、html 渲染等多路径回退
#
# 架构位置：
#     - 被调用：server/api/export.py
#     - 调用：server/memory/structured/、bibliography、theory_workspace
#
# 阅读提示：
#     - 新人先看 builder.collect_export_entries 再跟 docx/pdf 链路
#
# Debug：
#     - 导出失败 → 优先检查 pandoc / 字体 / 临时目录权限
# =============================================================================
