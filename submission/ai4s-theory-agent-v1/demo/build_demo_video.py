#!/usr/bin/env python3
"""Generate ≤3min Chinese caption demo MP4 for AI4S submission."""
from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/home/agent/submission/ai4s-theory-agent-v1")
FRAMES = ROOT / "demo" / "frames"
OUT = ROOT / "demo" / "AI4S-智能体演示-3min.mp4"
FONT = ROOT / "demo" / "assets" / "fonts" / "wqy-microhei.ttc"

W, H = 1280, 720
FPS = 1  # 1 fps, duration per slide in seconds via repeat

# (duration_sec, title, lines)
SLIDES: list[tuple[int, str, list[str]]] = [
    (
        12,
        "AI4S 理论侧多智能体",
        [
            "文献检索 · 理论推导 · 实验顾问",
            "提交演示 · 运行全过程概览",
            "产品版本 v2.2",
        ],
    ),
    (
        16,
        "六种智能体角色",
        [
            "general  总览分流",
            "literature  文献与方法卡",
            "theory  形式化推导与定理库",
            "experiment  实验计划 / 读数 / 下一步",
            "review / counterexample  审稿与反例",
            "边界：不代训模型、不大规模实跑",
        ],
    ),
    (
        18,
        "能力闭环",
        [
            "literature → MethodCard（方法卡）",
            "→ theory → DerivationTrace（推导迹）+ L4 定理",
            "→ experiment → ExperimentPlan",
            "用户提交 DataPacket → NextStepMemo",
            "人机共改：定理库 / 计划 / 图谱可编辑",
        ],
    ),
    (
        16,
        "系统界面结构",
        [
            "左侧：会话 · 课题 · 任务看板",
            "中间：多轮对话（SSE 流式 + 工具调用）",
            "右侧工作台：",
            "  文献 | 理论 | 验证 | 产出",
            "访问：浏览器打开服务地址（如 :8000）",
        ],
    ),
    (
        20,
        "全过程① 文献 → 方法卡",
        [
            "1. 新建会话并关联默认课题",
            "2. 文献 Tab 上传真实 PDF（或 arXiv）",
            "3. 选用 literature，发送 /method 提炼",
            "4. 回答末尾产出 artifact:MethodCard",
            "5. 右侧「方法卡」面板可见落盘结果",
        ],
    ),
    (
        22,
        "全过程② 理论推导",
        [
            "1. 场景可自动接 theory，或手动指定 theory",
            "2. 对照 symbols / assumptions 形式化",
            "3. 产出 DerivationTrace（分步 + 待验证标记）",
            "4. ## 引理/定理 自动写入 L4 定理库",
            "5. 可查看关系图谱与手工修订条目",
        ],
    ),
    (
        20,
        "全过程③ 实验顾问",
        [
            "1. 指定 experiment 生成 ExperimentPlan",
            "2. 用户本机实验后回传 metrics / 表格",
            "3. 系统写入 DataPacket 并解读",
            "4. 产出 NextStepMemo：支持/反驳/缺数/下一步",
            "5. 计划与建议支持人工 CRUD",
        ],
    ),
    (
        16,
        "记忆与远程调用",
        [
            "L1 工作记忆 · L2 会话 · L3 RAG · L4 定理库",
            "主接口：POST /v1/chat/stream（SSE）",
            "文档入库 / 定理 CRUD / Artifacts API",
            "健康检查：GET /health",
            "详见设计文档与后续部署说明",
        ],
    ),
    (
        14,
        "总结",
        [
            "理论侧多智能体：读文献 → 推理论 → 管实验建议",
            "结构化工件可复查、可导出、可人工修正",
            "不替代完整训练流水线",
            "感谢观看",
        ],
    ),
]


def wrap_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size=size)


def render_slide(title: str, lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), (18, 28, 48))
    draw = ImageDraw.Draw(img)
    # accent bar
    draw.rectangle([0, 0, 16, H], fill=(56, 189, 248))
    draw.rectangle([0, H - 8, W, H], fill=(56, 189, 248))

    title_font = wrap_font(44)
    body_font = wrap_font(30)
    small = wrap_font(22)

    draw.text((56, 48), title, font=title_font, fill=(248, 250, 252))
    y = 140
    for line in lines:
        draw.text((56, y), line, font=body_font, fill=(226, 232, 240))
        y += 52

    draw.text((56, H - 56), "AI4S Research Agent  ·  提交演示", font=small, fill=(148, 163, 184))
    return img


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []
    total = 0
    for i, (dur, title, lines) in enumerate(SLIDES, 1):
        im = render_slide(title, lines)
        path = FRAMES / f"slide_{i:02d}.png"
        im.save(path)
        arr = np.asarray(im)
        for _ in range(dur):
            frames.append(arr)
        total += dur
        print(f"slide {i}: {dur}s — {title}")

    print("total_seconds", total)
    # write mp4 via imageio-ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    writer = imageio.get_writer(
        str(OUT),
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
        ffmpeg_log_level="error",
    )
    # imageio may need ffmpeg path via env; set plugin
    for fr in frames:
        writer.append_data(fr)
    writer.close()
    print("wrote", OUT, "size", OUT.stat().st_size)
    print("ffmpeg", ffmpeg)


if __name__ == "__main__":
    main()
