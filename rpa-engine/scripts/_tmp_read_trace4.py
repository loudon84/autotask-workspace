"""临时：dump trace 最后 N 个事件的原始 JSON。"""
import json
import sys

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
events = []
with open(path, encoding="utf-8") as f:
    for line in f:
        try:
            events.append(json.loads(line))
        except Exception:
            pass
for e in events[-n:]:
    if e.get("type") in ("screencast-frame", "frame-snapshot"):
        print(e.get("type"), "(skipped)")
        continue
    print(json.dumps(e, ensure_ascii=False)[:1200])
    print("---")
