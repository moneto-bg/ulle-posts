"""Approve a staged post and publish it.

    python3 -m pipeline.approve <id> [<id> ...]
    python3 -m pipeline.approve --list

Publishing runs through publish.py (Meta Graph API when tokens exist, else a
manual handoff into state/approved/<id>/). On success the post moves to
state/published/<id>/.
"""
from __future__ import annotations

import json
import shutil
import sys

from . import common, publish as publish_mod


def list_pending() -> None:
    common.ensure_dirs()
    rows = sorted(common.QUEUE.glob("*/plan.json"))
    if not rows:
        print("Няма чакащи постове.")
        return
    print("Чакащи за одобрение:")
    for pj in rows:
        plan = json.loads(pj.read_text(encoding="utf-8"))
        print(f"  {plan['id']}  „{plan['copy'].get('headline','')}“  ({plan['scene']})")


def approve(post_id: str) -> None:
    d = common.QUEUE / post_id
    plan_path = d / "plan.json"
    post_png = d / "post.png"
    if not plan_path.exists() or not post_png.exists():
        print(f"Не намирам готов пост {post_id} в опашката.")
        return
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cfg = common.load_config()
    results = publish_mod.publish_post(plan, str(post_png), cfg)

    dest = common.PUBLISHED / post_id
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(d), str(dest))
    (dest / "publish_result.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {post_id} обработен: {json.dumps(results, ensure_ascii=False)}")


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0] in ("--list", "-l"):
        list_pending()
        return 0
    for pid in args:
        approve(pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
