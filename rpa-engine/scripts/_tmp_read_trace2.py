"""临时：完整解析 trace —— 事件类型统计 + 所有含 error 的事件 + 时间线。"""
import json
import sys
from collections import Counter

path = sys.argv[1]
events = []
with open(path, encoding="utf-8") as f:
    for line in f:
        try:
            events.append(json.loads(line))
        except Exception:
            pass

print("types:", Counter(e.get("type") for e in events))

# 所有含 error 字样的事件
for e in events:
    blob = json.dumps(e, ensure_ascii=False)
    if "error" in blob.lower() and e.get("type") not in ("context-options",):
        print("\n== ERR-EVENT type=", e.get("type"), "api=", e.get("apiName"))
        print(blob[:1500])

# before 事件的完整时间线（含 apiName 真实字段名探测）
print("\n== 样例 before 事件全字段 ==")
for e in events:
    if e.get("type") == "before":
        print(json.dumps(e, ensure_ascii=False)[:800])
        break

# after 事件里带 error 的
print("\n== after 事件 error 字段探测 ==")
for e in events:
    if e.get("type") == "after" and e.get("error"):
        print(json.dumps(e, ensure_ascii=False)[:800])
