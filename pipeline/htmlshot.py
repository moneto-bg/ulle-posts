"""Render an HTML file to a PNG using the system Chrome headless. Zero deps."""
from __future__ import annotations

import shutil
import subprocess
import pathlib

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if pathlib.Path(c).exists():
            return c
    for name in ("google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


def html_to_png(html_path: str | pathlib.Path, out_path: str | pathlib.Path,
                width: int, height: int) -> str:
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("No Chrome/Chromium found for HTML rendering.")
    html_path = pathlib.Path(html_path).resolve()
    out_path = pathlib.Path(out_path).resolve()
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--screenshot={out_path}", f"--window-size={width},{height}",
        "--default-background-color=ffffffff",
        f"file://{html_path}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not out_path.exists():
        raise RuntimeError(f"Chrome did not produce {out_path}\n{proc.stderr[:800]}")
    return str(out_path)
