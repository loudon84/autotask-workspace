"""临时：trace 完整时间线（class.method + selector + 耗时 + 错误）。"""
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

calls = {}
for e in events:
    t = e.get("type")
    if t == "before":
        calls[e.get("callId")] = e
    elif t == "after":
        cid = e.get("callId")
        before = calls.get(cid, {})
        method = f"{before.get('class')}.{before.get('method')}"
        sel = (before.get("params") or {}).get("selector", "")
        dur = ""
        if before.get("startTime") and e.get("endTime"):
            dur = f"{(e['endTime'] - before['startTime'])/1000:.1f}s"
        err = e.get("error") or ""
        print(f"{method:40s} {dur:>7s} {sel[:100]}")
        if err:
            print("   ERROR:", json.dumps(err, ensure_ascii=False)[:500])
    elif t == "event":
        print("EVENT:", json.dumps(e, ensure_ascii=False)[:300])
