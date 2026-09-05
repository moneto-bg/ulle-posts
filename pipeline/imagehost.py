"""Publish a finished PNG to a public URL so Instagram can fetch it.

Instagram's Content Publishing API needs a public image URL (it downloads the
image itself). This uploads the local PNG to a public GitHub repo via the
GitHub Contents API (no git clone, no gh CLI) and returns the raw URL.

Config: config.json -> image_host: {type:"github", owner, repo, branch, path}
Secret: .env -> GITHUB_TOKEN (fine-grained PAT with Contents: Read & write on the
repo, or a classic token with the `public_repo` scope).

A static host can be used instead by setting PUBLIC_IMAGE_BASE in .env; then this
module isn't needed.
"""
from __future__ import annotations

import base64
import json
import os
import pathlib
import urllib.error
import urllib.request

from . import common


def _github_upload(local_path: str, host: dict, token: str) -> str:
    owner = host["owner"]; repo = host["repo"]
    branch = host.get("branch", "main")
    folder = host.get("path", "").strip("/")
    name = pathlib.Path(local_path).name
    repo_path = f"{folder}/{name}" if folder else name

    content_b64 = base64.b64encode(pathlib.Path(local_path).read_bytes()).decode("ascii")
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{repo_path}"
    payload = {"message": f"post image {name}", "content": content_b64, "branch": branch}

    # If the file already exists we must send its sha to overwrite it.
    try:
        get = urllib.request.Request(f"{api}?ref={branch}",
                                     headers={"Authorization": f"Bearer {token}",
                                              "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(get, timeout=30) as r:
            payload["sha"] = json.loads(r.read().decode())["sha"]
    except urllib.error.HTTPError:
        pass  # 404 = new file, fine

    req = urllib.request.Request(
        api, data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub upload {e.code}: {e.read().decode('utf-8','replace')[:300]}")

    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{repo_path}"


def upload_public(local_path: str, cfg: dict) -> str | None:
    """Return a public URL for the image, or None if no host is configured."""
    common.load_env()
    base = os.environ.get("PUBLIC_IMAGE_BASE")
    if base:
        return base.rstrip("/") + "/" + pathlib.Path(local_path).name
    host = cfg.get("image_host", {})
    if host.get("type") == "github" and host.get("owner") and host.get("repo"):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN липсва в .env")
        return _github_upload(local_path, host, token)
    return None
