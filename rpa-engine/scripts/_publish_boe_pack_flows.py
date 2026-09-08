"""Build + publish the three BOE invoice-packing flows (enrich/save_draft/submit) 1.0.0.

Usage: uv run python scripts/_publish_boe_pack_flows.py
Requires Engine on 127.0.0.1:4610. Writes rpa-flows/<flow>/_publish_1.0.0.json per flow.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
DIST = FLOWS / "dist"
FILES = ("manifest.json", "selectors.json", "flow.py")

BOE_FLOWS = [
    ("rpa_flow_srm_boe_pack_enrich", "srm_boe_pack_enrich"),
    ("rpa_flow_srm_boe_pack_save_draft", "srm_boe_pack_save_draft"),
    ("rpa_flow_srm_boe_pack_submit", "srm_boe_pack_submit"),
]
VERSION = "1.0.23"


def build(flow_id: str) -> Path:
    src = FLOWS / flow_id / VERSION
    DIST.mkdir(parents=True, exist_ok=True)
    zip_path = DIST / f"{flow_id}-{VERSION}.zip"
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


def publish_one(client: httpx.Client, flow_id: str, workflow_code: str) -> dict:
    zip_path = build(flow_id)
    with zip_path.open("rb") as fh:
        resp = client.post(
            f"{ENGINE}/api/v1/flows/packages",
            headers=HEADERS,
            files={"package": (zip_path.name, fh, "application/zip")},
            data={
                "scope": "GLOBAL",
                "description": f"{flow_id} {VERSION} BOE invoice packing",
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
        json={"reason": f"publish {flow_id} {VERSION} BOE invoice packing"},
    )
    print(flow_id, "publish", pub.status_code, pub.text[:250])
    pub.raise_for_status()
    published = pub.json()
    out = {
        "rpaFlowId": flow_id,
        "rpaFlowVersion": published.get("version") or VERSION,
        "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
        "packageChecksum": published.get("packageChecksum") or checksum,
        "status": published.get("status"),
        "workflowCode": workflow_code,
    }
    path = FLOWS / flow_id / f"_publish_{VERSION}.json"
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
    results = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for flow_id, workflow_code in BOE_FLOWS:
            results.append(publish_one(client, flow_id, workflow_code))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
