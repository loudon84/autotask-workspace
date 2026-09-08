"""临时：解析 Playwright trace，列出所有动作与失败点。"""
import json
import sys

path = sys.argv[1]
events = []
with open(path, encoding="utf-8") as f:
    for line in f:
        try:
            events.append(json.loads(line))
        except Exception:
            pass
print("events:", len(events))
for e in events:
    t = e.get("type")
    if t == "before":
        sel = (e.get("params") or {}).get("selector", "")
        print("BEFORE", e.get("apiName"), "|", sel[:140])
    elif t == "after":
        err = (e.get("error") or {}).get("error", {}).get("message", "")
        status = "ERR " if err else "ok  "
        print("AFTER", status, e.get("apiName"), "|", err[:400].replace("\n", " / "))
