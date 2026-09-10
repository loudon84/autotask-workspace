"""Build + publish BOE invoice-packing flows.

Usage:
  uv run python scripts/_publish_boe_pack_flows.py                 # enrich/save/submit 1.0.23 + delete 1.0.0
  uv run python scripts/_publish_boe_pack_flows.py --only-delete   # delete_draft 1.0.1 only

Requires Engine on 127.0.0.1:4610. Writes rpa-flows/<flow>/_publish_<ver>.json per flow.
Do not re-run the default path just to add delete_draft — that would re-upload 1.0.23.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
DIST = FLOWS / "dist"
FILES = ("manifest.json", "selectors.json", "flow.py")

PACK_FLOWS = [
    ("rpa_flow_srm_boe_pack_enrich", "srm_boe_pack_enrich", "1.0.23"),
    ("rpa_flow_srm_boe_pack_save_draft", "srm_boe_pack_save_draft", "1.0.23"),
    ("rpa_flow_srm_boe_pack_submit", "srm_boe_pack_submit", "1.0.23"),
]
DELETE_FLOW = ("rpa_flow_srm_boe_pack_delete_draft", "srm_boe_pack_delete_draft", "1.0.1")


def build(flow_id: str, version: str) -> Path:
    src = FLOWS / flow_id / version
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / f"{flow_id}-{version}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            entry = zipfile.ZipInfo(name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0o100666 << 16
            archive.writestr(entry, (src / name).read_bytes())
    print(f"built {zip_path} ({zip_path.stat().st_size} bytes)")
    return zip_path


def publish_one(client: httpx.Client, flow_id: str, workflow_code: str, version: str) -> dict:
    zip_path = build(flow_id, version)
    with zip_path.open("rb") as fh:
        resp = client.post(
            f"{ENGINE}/api/v1/flows/packages",
            headers=HEADERS,
            files={"package": (zip_path.name, fh, "application/zip")},
            data={
                "scope": "GLOBAL",
                "description": f"{flow_id} {version} BOE invoice packing",
            },
        )
    print(flow_id, "upload", resp.status_code, resp.text[:300])
    resp.raise_for_status()
    version_body = resp.json()["version"]
    version_id = version_body["rpaFlowVersionId"]
    checksum = version_body["packageChecksum"]
    val = client.post(
        f"{ENGINE}/api/v1/flow-versions/{version_id}/validate",
        headers=HEADERS,
    )
    print(flow_id, "validate", val.status_code, val.json().get("status"))
    val.raise_for_status()
    pub = client.post(
        f"{ENGINE}/api/v1/flow-versions/{version_id}/publish",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"reason": f"publish {flow_id} {version} BOE invoice packing"},
    )
    print(flow_id, "publish", pub.status_code, pub.text[:250])
    pub.raise_for_status()
    published = pub.json()
    out = {
        "rpaFlowId": flow_id,
        "rpaFlowVersion": published.get("version") or version,
        "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
        "packageChecksum": published.get("packageChecksum") or checksum,
        "status": published.get("status"),
        "workflowCode": workflow_code,
    }
    path = FLOWS / flow_id / f"_publish_{version}.json"
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", path)
    vb = client.post(
        f"{ENGINE}/api/v1/flow-versions/validate-binding",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "rpaFlowId": flow_id,
            "rpaFlowVersion": out["rpaFlowVersion"],
            "workflowCode": workflow_code,
        },
    )
    print(flow_id, "validate-binding", vb.status_code, vb.text[:200])
    vb.raise_for_status()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only-delete",
        action="store_true",
        help="只发布 rpa_flow_srm_boe_pack_delete_draft 1.0.1，不重传 1.0.23",
    )
    args = parser.parse_args()
    targets = [DELETE_FLOW] if args.only_delete else [*PACK_FLOWS, DELETE_FLOW]
    results = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for flow_id, workflow_code, version in targets:
            results.append(publish_one(client, flow_id, workflow_code, version))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
