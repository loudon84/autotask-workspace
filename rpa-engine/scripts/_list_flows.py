"""List Engine flows without printing secrets."""

import json

import httpx

resp = httpx.get(
    "http://127.0.0.1:4610/api/v1/flows",
    headers={"X-Actor-Id": "flow-registry-operator"},
    timeout=10,
)
resp.raise_for_status()
data = resp.json()
items = data.get("items") or data.get("data") or data
if isinstance(items, dict):
    items = items.get("items") or [items]
print("count", len(items) if isinstance(items, list) else type(items))
if isinstance(items, list):
    for item in items:
        if not isinstance(item, dict):
            print(item)
            continue
        print(
            item.get("rpaFlowId") or item.get("rpa_flow_id"),
            item.get("latestPublishedVersion") or item.get("version"),
            item.get("status"),
        )
