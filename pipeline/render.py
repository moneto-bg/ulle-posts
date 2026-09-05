"""Render the scene WITH the shirt, generated from the reference photo.

Full-generative: OpenAI gpt-image-1 image edit takes the reference shirt photo and
generates a new scene around it, integrating the garment with real light. The
prompt pushes hard to keep the shirt identical, though fine text (label/logo) can
still drift slightly - that trade-off was chosen deliberately. urllib only.
Falls back to a labelled gradient + the real shirt when OPENAI_API_KEY is absent.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import pathlib
import urllib.error
import urllib.request
import uuid

from . import common, htmlshot

OPENAI_EDIT_URL = "https://api.openai.com/v1/images/edits"


def _multipart(fields: dict[str, str], files: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----ulle" + uuid.uuid4().hex
    out = bytearray()
    for name, val in fields.items():
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        out += f"{val}\r\n".encode()
    for name, path in files.items():
        p = pathlib.Path(path)
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        out += f"--{boundary}\r\n".encode()
        out += (f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{p.name}"\r\n').encode()
        out += f"Content-Type: {mime}\r\n\r\n".encode()
        out += p.read_bytes()
        out += b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), boundary


def _render_openai(bg_prompt: dict, ref_path: str, out_path: str, cfg: dict) -> str:
    key = os.environ["OPENAI_API_KEY"]
    rcfg = cfg.get("render", {})
    fields = {
        "model": rcfg.get("model", "gpt-image-1"),
        "prompt": bg_prompt["prompt_string"],
        "size": rcfg.get("size", "1024x1536"),
    }
    if rcfg.get("quality"):
        fields["quality"] = rcfg["quality"]
    if rcfg.get("input_fidelity"):
        fields["input_fidelity"] = rcfg["input_fidelity"]  # 'high' keeps the ref sharper
    data, boundary = _multipart(fields, {"image": ref_path})
    req = urllib.request.Request(
        OPENAI_EDIT_URL, data=data,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:600]}")
    b64 = payload["data"][0]["b64_json"]
    pathlib.Path(out_path).write_bytes(base64.b64decode(b64))
    return out_path


def _render_placeholder(bg_prompt: dict, ref_path: str, out_path: str) -> str:
    tone = bg_prompt.get("text_zone", {}).get("tone", "mid")
    grad = {"dark": "#20303a,#0d1418", "mid-dark": "#2a6b73,#0f2d33",
            "light": "#e7dcc8,#c9a98c", "mid-light": "#d9cbb2,#a98d6d"}.get(
        tone, "#c9a98c,#8c9377")
    ref_uri = pathlib.Path(ref_path).resolve().as_uri()
    concept = bg_prompt.get("meta", {}).get("concept_bg", "")
    html = f"""<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0}} .f{{width:1080px;height:1350px;position:relative;overflow:hidden;
background:linear-gradient(135deg,{grad});font-family:-apple-system,sans-serif}}
.f img{{position:absolute;left:50%;top:56%;transform:translate(-50%,-50%);
width:74%;filter:drop-shadow(0 30px 60px rgba(0,0,0,.35))}}
.tag{{position:absolute;left:0;right:0;bottom:14px;text-align:center;color:#fff9;
font-size:20px;letter-spacing:2px}}</style>
<div class="f"><img src="{ref_uri}"><div class="tag">PLACEHOLDER · {concept} · добави OPENAI_API_KEY за реален фон</div></div>"""
    tmp = pathlib.Path(out_path).with_suffix(".placeholder.html")
    tmp.write_text(html, encoding="utf-8")
    htmlshot.html_to_png(tmp, out_path, 1080, 1350)
    tmp.unlink(missing_ok=True)
    return out_path


def render_background(bg_prompt: dict, out_path: str, cfg: dict) -> tuple[str, bool]:
    """Return (path, is_real). is_real=False means a placeholder was used."""
    common.load_env()
    ref_path = bg_prompt["reference"]["product_image"]
    if not pathlib.Path(ref_path).exists():
        raise FileNotFoundError(f"reference image not found: {ref_path}")
    if os.environ.get("OPENAI_API_KEY") and cfg.get("render", {}).get("engine") == "openai":
        common.log("render_openai", id=bg_prompt["id"])
        return _render_openai(bg_prompt, ref_path, out_path, cfg), True
    common.log("render_placeholder", id=bg_prompt["id"], reason="no OPENAI_API_KEY")
    return _render_placeholder(bg_prompt, ref_path, out_path), False
