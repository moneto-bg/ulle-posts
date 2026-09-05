"""Place ONLY the ULLE logo (top-centre) over the generated background.

No text is drawn on the image - all copy goes into the post caption (see
common.build_caption). Uses the HTML template + Chrome headless.
"""
from __future__ import annotations

import pathlib

from . import common, htmlshot

TEMPLATE = common.ROOT / "templates" / "post.html.tmpl"


def compose(plan: dict, bg_png: str, out_png: str, cfg: dict, show_logo: bool = True) -> str:
    ov = cfg.get("overlay", {})
    logo_uri = (common.ROOT / cfg.get("paths", {}).get("logo", "assets/ULLE-LOGO.png")).resolve().as_uri()

    tmpl = TEMPLATE.read_text(encoding="utf-8")
    repl = {
        "__BG_URI__": pathlib.Path(bg_png).resolve().as_uri(),
        "__LOGO_URI__": logo_uri,
        "__LOGO_W__": str(ov.get("logo_width", 200)),
        "__LOGO_TOP__": str(ov.get("logo_top", 56)),
    }
    for k, v in repl.items():
        tmpl = tmpl.replace(k, v)

    html_path = pathlib.Path(out_png).with_suffix(".compose.html")
    html_path.write_text(tmpl, encoding="utf-8")
    w = cfg.get("output", {}).get("width", 1080)
    h = cfg.get("output", {}).get("height", 1350)
    htmlshot.html_to_png(html_path, out_png, w, h)
    html_path.unlink(missing_ok=True)
    common.log("overlay_done", id=plan["id"])
    return out_png
