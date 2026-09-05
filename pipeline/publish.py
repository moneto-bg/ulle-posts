"""Approval-gated publishing.

Safety: publishing to public accounts is gated. run_daily.py never publishes; it
stages a post for review. A human runs approve.py, which calls publish_post().

Backends, chosen by what's in .env:
  - Facebook Page:  binary upload to /{FB_PAGE_ID}/photos  (needs FB_PAGE_ID, FB_PAGE_TOKEN)
  - Instagram:      two-step create+publish; needs a PUBLIC image URL, so it needs
                    IG_USER_ID, IG_TOKEN and PUBLIC_IMAGE_BASE (a URL that serves
                    the final PNG). Without PUBLIC_IMAGE_BASE, IG falls back to manual.
  - Manual:         no tokens -> copy the post + caption to state/approved and tell
                    the user to upload. This is the default until tokens are provided.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import urllib.error
import urllib.request
import uuid

from . import common, imagehost

GRAPH = "https://graph.facebook.com/v21.0"


def _caption(plan: dict) -> str:
    return common.build_caption(plan)


def _fb_photo(page_id: str, token: str, img: str, caption: str) -> dict:
    boundary = "----ulle" + uuid.uuid4().hex
    p = pathlib.Path(img)
    body = bytearray()
    for name, val in {"caption": caption, "access_token": token}.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode()
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"source\"; "
             f"filename=\"{p.name}\"\r\nContent-Type: image/png\r\n\r\n").encode()
    body += p.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{GRAPH}/{page_id}/photos", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _ig_publish(ig_user: str, token: str, image_url: str, caption: str) -> dict:
    import urllib.parse
    create = urllib.request.Request(
        f"{GRAPH}/{ig_user}/media",
        data=urllib.parse.urlencode({"image_url": image_url, "caption": caption,
                                     "access_token": token}).encode(), method="POST")
    with urllib.request.urlopen(create, timeout=120) as resp:
        cid = json.loads(resp.read().decode("utf-8"))["id"]
    pub = urllib.request.Request(
        f"{GRAPH}/{ig_user}/media_publish",
        data=urllib.parse.urlencode({"creation_id": cid, "access_token": token}).encode(),
        method="POST")
    with urllib.request.urlopen(pub, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def publish_post(plan: dict, final_png: str, cfg: dict) -> dict:
    common.load_env()
    caption = _caption(plan)
    results: dict[str, str] = {}
    platforms = plan.get("platforms", cfg.get("platforms", []))

    fb_id, fb_tok = os.environ.get("FB_PAGE_ID"), os.environ.get("FB_PAGE_TOKEN")
    ig_id, ig_tok = os.environ.get("IG_USER_ID"), os.environ.get("IG_TOKEN")
    pub_base = os.environ.get("PUBLIC_IMAGE_BASE")

    if "facebook" in platforms and fb_id and fb_tok:
        try:
            r = _fb_photo(fb_id, fb_tok, final_png, caption)
            results["facebook"] = f"ok:{r.get('post_id') or r.get('id')}"
        except urllib.error.HTTPError as e:
            results["facebook"] = f"error:{e.read().decode('utf-8','replace')[:200]}"

    if "instagram" in platforms and ig_id and ig_tok:
        try:
            image_url = imagehost.upload_public(final_png, cfg)
            if not image_url:
                results["instagram"] = "manual:need image_host(github) or PUBLIC_IMAGE_BASE"
            else:
                r = _ig_publish(ig_id, ig_tok, image_url, caption)
                results["instagram"] = f"ok:{r.get('id')}"
        except urllib.error.HTTPError as e:
            results["instagram"] = f"error:{e.read().decode('utf-8','replace')[:200]}"
        except RuntimeError as e:
            results["instagram"] = f"error:{e}"
    elif "instagram" in platforms:
        results["instagram"] = "manual:need IG_USER_ID+IG_TOKEN"

    # Anything not published automatically -> manual handoff.
    if not results or all(v.startswith("manual") for v in results.values()):
        dest = common.APPROVED / plan["id"]
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(final_png, dest / "post.png")
        (dest / "caption.txt").write_text(caption, encoding="utf-8")
        (dest / "post.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        results["manual"] = str(dest)

    common.log("published", id=plan["id"], results=json.dumps(results, ensure_ascii=False))
    return results
