"""Daily orchestrator: plan -> ulle-backgrounds prompt -> render -> overlay -> stage for approval.

In approval mode (default) this NEVER publishes. It stages a finished post under
state/queue/<id>/ and opens it for review. Approve with:  python3 -m pipeline.approve <id>
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

from . import common, plan as plan_mod, render as render_mod, overlay as overlay_mod


def _validate(bg_json_path: pathlib.Path, cfg: dict) -> None:
    checker = pathlib.Path(cfg["paths"]["skill_dir"]) / "scripts" / "check_background.py"
    if not checker.exists():
        return
    r = subprocess.run([sys.executable, str(checker), str(bg_json_path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        common.log("bg_validation_warn", id=bg_json_path.parent.name, out=r.stdout[-300:])


def _notify(title: str, msg: str, open_path: str | None = None) -> None:
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}"'], check=False)
    except Exception:
        pass
    if open_path:
        subprocess.run(["open", open_path], check=False)


def _schedule_guard(cfg: dict) -> bool:
    """True if we should run now.

    Cloud cron fires in UTC, so we over-schedule it and let this check the real
    local (Europe/Sofia) hour against schedule.times. Keeps 10:00/19:00 exact
    across summer/winter time. Skipped unless ULLE_GUARD_SCHEDULE=1.
    """
    import os
    if os.environ.get("ULLE_GUARD_SCHEDULE") != "1":
        return True
    sched = cfg.get("schedule", {})
    times = sched.get("times") or [sched.get("time", "10:00")]
    now = common.now_local(cfg)
    for t in times:
        h, m = (int(x) for x in t.split(":"))
        if now.hour == h:
            return True
    common.log("skipped_not_scheduled", local_time=now.strftime("%Y-%m-%d %H:%M"),
               expected=",".join(times))
    return False


def run(cfg: dict | None = None) -> list[dict]:
    cfg = cfg or common.load_config()
    common.load_env()
    if not _schedule_guard(cfg):
        return []
    common.ensure_dirs()
    results = []
    for _ in range(int(cfg.get("schedule", {}).get("posts_per_run", 1))):
        n = common.next_slot(cfg)  # unique per run, so 10:00 and 19:00 never collide
        p = plan_mod.make_plan(cfg, n)
        d = common.QUEUE / p["id"]
        d.mkdir(parents=True, exist_ok=True)

        bg_json = d / "bg.json"
        bg_json.write_text(json.dumps(p["bg_prompt"], ensure_ascii=False, indent=2), encoding="utf-8")
        _validate(bg_json, cfg)

        bg_png = str(d / "background.png")
        _, is_real = render_mod.render_background(p["bg_prompt"], bg_png, cfg)

        post_png = str(d / "post.png")
        # Every post = generated photo + ULLE logo top-centre, no other text.
        overlay_mod.compose(p, bg_png, post_png, cfg)

        (d / "plan.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
        (d / "caption.txt").write_text(common.build_caption(p), encoding="utf-8")
        (d / "status").write_text("pending" if cfg.get("publish", {}).get("mode") == "approval" else "auto",
                                  encoding="utf-8")

        common.log("staged", id=p["id"], scene=p["scene"], layout=p.get("layout"),
                   real_render=is_real, headline=p["copy"].get("headline", ""))
        results.append({"id": p["id"], "dir": str(d), "post": post_png,
                        "real_render": is_real, "headline": p["copy"].get("headline", "")})

    if cfg.get("publish", {}).get("mode") == "approval" and results:
        first = results[0]
        note = "" if first["real_render"] else "  (PLACEHOLDER — добави OPENAI_API_KEY)"
        _notify("ULLE пост за одобрение", f'{first["headline"]}{note}', first["post"])
        print("\n=== Готови постове за одобрение ===")
        for r in results:
            print(f"  {r['id']}  „{r['headline']}“  ->  {r['post']}"
                  + ("" if r["real_render"] else "  [PLACEHOLDER]"))
        print("\nОдобри и публикувай:  python3 -m pipeline.approve <id>")
    return results


if __name__ == "__main__":
    run()
