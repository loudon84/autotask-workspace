from __future__ import annotations

import re
from pathlib import Path

import httpx

OUT = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\demo-captcha")
OUT.mkdir(parents=True, exist_ok=True)

html = httpx.get("http://192.168.102.247:3000/", timeout=15.0, trust_env=False).text
(OUT / "home.html").write_text(html, encoding="utf-8")
print("html_len", len(html))
for kind, pattern in (
    ("src", r"""src=["']([^"']+)["']"""),
    ("href", r"""href=["']([^"']+)["']"""),
):
    for item in re.findall(pattern, html):
        print(kind, item)
