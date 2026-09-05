"""Discover Facebook Page ID + Instagram Business ID from a token in .env and
write them back into .env. Zero third-party deps.

Usage:
  1) put your token in .env on the line  FB_PAGE_TOKEN=...   (a User or Page token)
  2) run:  python3 -m pipeline.setup_meta

It reads the token, asks the Graph API which Page(s) and Instagram account(s) it
can post to, prints them, and fills FB_PAGE_ID / FB_PAGE_TOKEN / IG_USER_ID /
IG_TOKEN in .env. It never posts anything.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from . import common

GRAPH = "https://graph.facebook.com/v21.0"


def _get(path: str, token: str, fields: str = "") -> dict:
    q = {"access_token": token}
    if fields:
        q["fields"] = fields
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(q)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _set_env(key: str, val: str) -> None:
    lines = common.ENV_PATH.read_text(encoding="utf-8").splitlines() if common.ENV_PATH.exists() else []
    out, found = [], False
    for ln in lines:
        if re.match(rf"^\s*{re.escape(key)}\s*=", ln):
            out.append(f"{key}={val}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={val}")
    common.ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    common.load_env()
    # The discovery (User) token is kept in META_USER_TOKEN so re-runs keep working
    # even after we write page-specific tokens into FB_PAGE_TOKEN / IG_TOKEN.
    token = (os.environ.get("META_USER_TOKEN") or os.environ.get("FB_PAGE_TOKEN")
             or os.environ.get("META_TOKEN") or os.environ.get("IG_TOKEN") or "").strip()
    if not token:
        print("Сложи токена в .env на реда  META_USER_TOKEN=...  и пусни пак.")
        return 1
    _set_env("META_USER_TOKEN", token)  # preserve the original token for re-runs

    try:
        data = _get("me/accounts", token, "name,id,access_token,instagram_business_account")
    except urllib.error.HTTPError as e:
        print("Грешка от Meta:", e.read().decode("utf-8", "replace")[:400])
        return 1

    pages = data.get("data", [])
    if pages:
        print("Намерени страници:")
        for i, pg in enumerate(pages):
            iga = (pg.get("instagram_business_account") or {}).get("id")
            print(f"  [{i}] {pg.get('name')} | page_id={pg['id']} | instagram={iga or '-'}")
        idx = 0
        if len(pages) > 1 and len(sys.argv) > 1 and sys.argv[1].isdigit():
            idx = int(sys.argv[1])
        pg = pages[idx]
        _set_env("FB_PAGE_ID", pg["id"])
        if pg.get("access_token"):
            _set_env("FB_PAGE_TOKEN", pg["access_token"])
        iga = (pg.get("instagram_business_account") or {}).get("id")
        if iga:
            _set_env("IG_USER_ID", iga)
            _set_env("IG_TOKEN", pg.get("access_token", token))
        print(f"\n✓ Записах в .env страница „{pg.get('name')}“"
              + (f" + Instagram {iga}" if iga else " (без свързан Instagram Business)"))
        if len(pages) > 1:
            print("  (има повече от една страница — пусни `python3 -m pipeline.setup_meta <номер>` за друга)")
    else:
        try:
            me = _get("me", token, "id,name,instagram_business_account")
        except urllib.error.HTTPError as e:
            print("Токенът не вижда страници и не е Page токен:", e.read().decode("utf-8", "replace")[:300])
            return 1
        _set_env("FB_PAGE_ID", me["id"])
        print(f"Page токен: {me.get('name')} | page_id={me['id']}")
        iga = (me.get("instagram_business_account") or {}).get("id")
        if iga:
            _set_env("IG_USER_ID", iga)
            _set_env("IG_TOKEN", token)
            print(f"✓ Instagram Business: {iga}")

    if os.environ.get("IG_USER_ID") or "IG_USER_ID" in common.ENV_PATH.read_text(encoding="utf-8"):
        if not os.environ.get("PUBLIC_IMAGE_BASE"):
            print("\n⚠ За Instagram трябва и PUBLIC_IMAGE_BASE (публичен URL за картинката) в .env.")
    print("\nГотово. Кажи ми да проверя разрешенията и да пробвам (без да публикувам).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
