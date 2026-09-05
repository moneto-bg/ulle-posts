"""Open a GitHub Issue for a staged post so it can be approved with one comment.

Used by the cloud (GitHub Actions) flow: after generation the post files are
committed to the repo, then this opens an issue showing the image and caption.
Approve by commenting `ok` (or `публикувай`); reject with `не` / `skip`.

    python3 -m pipeline.gh_issue <post_id>

Needs GITHUB_TOKEN and GITHUB_REPOSITORY (both provided by Actions).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from . import common


def _api(path: str, token: str, payload: dict | None = None) -> dict:
    url = f"https://api.github.com/{path.lstrip('/')}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "ulle-automation",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def open_issue(post_id: str) -> str:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]          # owner/repo
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    d = common.QUEUE / post_id
    caption = (d / "caption.txt").read_text(encoding="utf-8") if (d / "caption.txt").exists() else ""
    img_url = (f"https://raw.githubusercontent.com/{repo}/{branch}/"
               f"state/queue/{post_id}/post.png")

    body = (
        f"![post]({img_url})\n\n"
        f"**Описание на поста:**\n\n"
        f"```\n{caption}\n```\n\n"
        f"---\n"
        f"➡️ Напиши **`ok`** в коментар, за да се публикува в Instagram.\n"
        f"➡️ Напиши **`не`**, за да се откаже.\n"
    )
    issue = _api(f"repos/{repo}/issues", token,
                 {"title": f"Пост за одобрение: {post_id}",
                  "body": body, "labels": ["post-approval"]})
    common.log("issue_opened", id=post_id, url=issue.get("html_url", ""))
    return issue.get("html_url", "")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python3 -m pipeline.gh_issue <post_id>")
        return 2
    try:
        print(open_issue(argv[1]))
    except urllib.error.HTTPError as e:
        print("GitHub error:", e.read().decode("utf-8", "replace")[:300])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
