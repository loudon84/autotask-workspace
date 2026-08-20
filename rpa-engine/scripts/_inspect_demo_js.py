from __future__ import annotations

import re

import httpx

BASE = "http://192.168.102.247:3000"
html = httpx.get(BASE + "/", timeout=15.0, trust_env=False).text
paths = sorted(set(re.findall(r"/static/js/[^\"']+\.js", html)))
print("js_files", len(paths))
client = httpx.Client(timeout=30.0, trust_env=False)
needles = ("code01", "code02", "login-captcha", "login_img", ".png", "mp3s")
for path in paths:
    text = client.get(BASE + path).text
    hits = [n for n in needles if n in text]
    if hits:
        print(path, "len", len(text), "hits", hits)
        for m in set(re.findall(r"[A-Za-z0-9_./%-]+\.png", text)):
            if "code" in m.lower() or "captcha" in m.lower() or "login" in m.lower():
                print("  png", m)
        for m in set(re.findall(r"/[^\"']{0,80}code0[0-9][^\"']{0,40}", text)):
            print("  code", m[:120])
