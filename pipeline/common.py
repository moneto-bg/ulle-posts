"""Shared helpers for the ULLE social automation pipeline. Zero third-party deps."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
ENV_PATH = ROOT / ".env"
STATE = ROOT / "state"
QUEUE = STATE / "queue"
APPROVED = STATE / "approved"
PUBLISHED = STATE / "published"
LOG = STATE / "log.jsonl"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_env() -> dict:
    """Read .env (KEY=VALUE lines) into os.environ without any dependency."""
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            env[key] = val
            os.environ.setdefault(key, val)
    return env


def now_local(cfg: dict) -> _dt.datetime:
    """Current time in the configured timezone (so cloud runners in UTC still
    schedule and date posts by Bulgarian time)."""
    tz_name = cfg.get("timezone")
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return _dt.datetime.now(ZoneInfo(tz_name))
        except Exception:
            pass
    return _dt.datetime.now()


def today(cfg: dict) -> _dt.date:
    return now_local(cfg).date()


def date_seed(cfg: dict, salt: str = "") -> int:
    """Deterministic per-day seed so a re-run of the same day is stable."""
    key = f"{today(cfg).isoformat()}|{salt}"
    return int(hashlib.sha256(key.encode()).hexdigest(), 16)


def pick_weighted(items: list[dict], seed: int, weight_key: str = "weight") -> dict:
    pool: list[dict] = []
    for it in items:
        pool.extend([it] * max(1, int(it.get(weight_key, 1))))
    return pool[seed % len(pool)]


def pick(items: list, seed: int):
    return items[seed % len(items)]


def post_id(cfg: dict, n: int = 1) -> str:
    return f"{today(cfg).isoformat()}-{n:02d}"


def next_slot(cfg: dict) -> int:
    """Next free slot number for today, so two runs a day never collide."""
    prefix = today(cfg).isoformat()
    used: set[int] = set()
    for base in (QUEUE, APPROVED, PUBLISHED):
        if not base.exists():
            continue
        for p in base.glob(f"{prefix}-*"):
            tail = p.name[len(prefix) + 1:]
            if tail.isdigit():
                used.add(int(tail))
    n = 1
    while n in used:
        n += 1
    return n


def log(event: str, **fields) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _dt.datetime.now().isoformat(timespec="seconds"), "event": event, **fields}
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{rec['ts']}] {event}: " + ", ".join(f"{k}={v}" for k, v in fields.items()),
          file=sys.stderr)


def ensure_dirs() -> None:
    for d in (QUEUE, APPROVED, PUBLISHED):
        d.mkdir(parents=True, exist_ok=True)


_COPY_TEXT_KEYS = ("headline", "accent", "post_title", "subhead", "caption", "badge")


def normalize_dashes(s: str) -> str:
    """Force the plain hyphen '-'; never em (—) or en (–) dashes."""
    if not isinstance(s, str):
        return s
    return s.replace("—", "-").replace("–", "-").replace("―", "-")


def clean_copy(copy: dict) -> dict:
    """Normalise dashes across all human-visible copy fields."""
    for k in _COPY_TEXT_KEYS:
        if isinstance(copy.get(k), str):
            copy[k] = normalize_dashes(copy[k])
    return copy


def build_caption(plan: dict) -> str:
    """The post caption, always in the same fixed structure:

        <creative hook - the only part that changes per post>

        ✅ benefit lines (from config.caption_template.benefits)

        <product page URL for the product in the post>

        <contact line>
        <signature>
    """
    c = plan.get("copy", {})
    hook = normalize_dashes((c.get("post_title") or c.get("headline") or "").strip())

    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    tpl = cfg.get("caption_template", {})

    blocks: list[str] = []
    if hook:
        blocks.append(hook)

    benefits = tpl.get("benefits", [])
    if benefits:
        blocks.append("\n".join(benefits))

    # Always the product page (not the landing page).
    url = (plan.get("product_url")
           or (plan.get("product") or {}).get("product_url")
           or plan.get("link", ""))
    if url:
        blocks.append(url)

    tail = [t for t in (tpl.get("contact"), tpl.get("signature")) if t]
    if tail:
        blocks.append("\n".join(tail))

    return "\n\n".join(blocks).strip()
