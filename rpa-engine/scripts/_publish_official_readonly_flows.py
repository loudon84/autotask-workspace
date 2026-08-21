"""Build + publish official-portal readonly Flow packages 1.1.1 to Engine Registry.

Do not bind these versions to demo portals (192.168.102.247).
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
VERSION = "1.1.1"
FILES = ("manifest.json", "selectors.json", "flow.py")
JOBS = [
    {
        "flow_id": "rpa_flow_srm_scan_pending_orders",
        "workflow": "srm_scan_pending_orders",
    },
    {
        "flow_id": "rpa_flow_srm_check_reply_status",
        "workflow": "srm_check_reply_status",
    },
    {
        "flow_id": "rpa_flow_srm_stmt_query_receipts",
        "workflow": "srm_stmt_query_receipts",
    },
]


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


def main() -> None:
    results: list[dict] = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for job in JOBS:
            zip_path = build(job["flow_id"])
            with zip_path.open("rb") as fh:
                resp = client.post(
                    f"{ENGINE}/api/v1/flows/packages",
                    headers=HEADERS,
                    files={"package": (zip_path.name, fh, "application/zip")},
                    data={
                        "scope": "GLOBAL",
                        "description": f"{job['flow_id']} {VERSION} (official portal)",
                    },
                )
            print("upload", job["flow_id"], resp.status_code, resp.text[:400])
            resp.raise_for_status()
            version_body = resp.json()["version"]
            version_id = version_body["rpaFlowVersionId"]
            checksum = version_body["packageChecksum"]
            print(" uploaded", version_body.get("version"), version_id, checksum)

            val = client.post(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/validate",
                headers=HEADERS,
            )
            print(" validate", val.status_code, val.json().get("status"))
            val.raise_for_status()

            pub = client.post(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/publish",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"reason": f"publish {job['flow_id']} {VERSION} official-portal"},
            )
            print("publish", job["flow_id"], pub.status_code, pub.text[:300])
            pub.raise_for_status()
            published = pub.json()
            out = {
                "rpaFlowId": job["flow_id"],
                "rpaFlowVersion": published.get("version") or VERSION,
                "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
                "packageChecksum": published.get("packageChecksum") or checksum,
                "status": published.get("status"),
                "workflowCode": job["workflow"],
            }
            path = FLOWS / job["flow_id"] / f"_publish_{VERSION}.json"
            path.write_text(
                json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("wrote", path)

            vb = client.post(
                f"{ENGINE}/api/v1/flow-versions/validate-binding",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={
                    "rpaFlowId": job["flow_id"],
                    "rpaFlowVersion": out["rpaFlowVersion"],
                    "workflowCode": job["workflow"],
                },
            )
            print("validate-binding", job["workflow"], vb.status_code, vb.text[:250])
            vb.raise_for_status()
            body = vb.json()
            if body.get("valid") is False:
                raise RuntimeError(f"validate-binding failed for {job['workflow']}: {body}")
            results.append(out)

    combined = FLOWS / "_publish_1.1.1.json"
    combined.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", combined)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
