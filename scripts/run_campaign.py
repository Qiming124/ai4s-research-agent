#!/usr/bin/env python3
"""CLI：列出/启动科研 Campaign 或调用 SkillsBridge。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保 app 包可导入
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from server.memory.campaigns import get_campaign_store  # noqa: E402
from server.memory.projects import get_project_store  # noqa: E402
from server.skills.bridge import get_skills_bridge  # noqa: E402


def cmd_list(args: argparse.Namespace) -> int:
    store = get_campaign_store()
    campaigns = store.list_campaigns(args.project_id)
    print(json.dumps(campaigns, ensure_ascii=False, indent=2))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = get_campaign_store()
    camp = store.get_campaign(args.campaign_id)
    if not camp:
        print(f"Campaign 不存在: {args.campaign_id}", file=sys.stderr)
        return 1
    print(json.dumps(camp, ensure_ascii=False, indent=2))
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    proj = get_project_store().resolve_project_id(args.project_id) or "default"
    store = get_campaign_store()
    camp = store.get_active_campaign(proj, args.campaign_id)
    if not camp:
        print("无活跃 Campaign", file=sys.stderr)
        return 1
    path = get_skills_bridge().bootstrap_campaign_artifact(proj, camp)
    print(json.dumps({"artifact_path": path, "campaign_id": camp["id"]}, ensure_ascii=False))
    return 0


def cmd_skills(_: argparse.Namespace) -> int:
    skills = get_skills_bridge().list_available_skills()
    print(json.dumps({"skills": skills}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="科研 Campaign CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出课题下 Campaign")
    p_list.add_argument("--project-id", default="default")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="显示 Campaign 详情")
    p_show.add_argument("campaign_id")
    p_show.set_defaults(func=cmd_show)

    p_boot = sub.add_parser("bootstrap", help="导出 Campaign 到 explore_outputs")
    p_boot.add_argument("--project-id", default="default")
    p_boot.add_argument("--campaign-id", default=None)
    p_boot.set_defaults(func=cmd_bootstrap)

    p_skills = sub.add_parser("skills", help="列出已安装的科研 skills")
    p_skills.set_defaults(func=cmd_skills)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
