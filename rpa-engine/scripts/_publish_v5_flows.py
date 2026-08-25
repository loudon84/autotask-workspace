"""Publish prepare 1.2.8 and upload 1.2.3, then print binding targets."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
DIST = FLOWS / "dist"

JOBS = [
    {
        "flow_id": "rpa_flow_supplier_portal_prepare_erp_order",
        "version": "1.2.8",
        "zip": DIST / "rpa_flow_supplier_portal_prepare_erp_order-1.2.8.zip",
        "workflow": "srm_prepare_erp_order",
        "existing_version_id": "52a1660f-6ff7-420b-84f7-e3afde0c0e12",
        "existing_checksum": "sha256:a9ce247cdfe5869ab23969140f7a79edcd3b1df83efbf43e0a794e903e264970",
    },
    {
        "flow_id": "rpa_flow_supplier_portal_upload_order_attachment",
        "version": "1.2.3",
        "zip": DIST / "rpa_flow_supplier_portal_upload_order_attachment-1.2.3.zip",
        "workflow": "srm_upload_order_attachment",
        "existing_version_id": None,
        "existing_checksum": None,
    },
]


def main() -> None:
    results: list[dict] = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for job in JOBS:
            version_id = job["existing_version_id"]
            checksum = job["existing_checksum"]
            version = job["version"]
            if not version_id:
                with job["zip"].open("rb") as fh:
                    resp = client.post(
                        f"{ENGINE}/api/v1/flows/packages",
                        headers=HEADERS,
                        files={"package": (job["zip"].name, fh, "application/zip")},
                        data={
                            "scope": "GLOBAL",
                            "description": f"{job['flow_id']} {job['version']}",
                        },
                    )
                print("upload", job["flow_id"], resp.status_code)
                resp.raise_for_status()
                version_body = resp.json()["version"]
                version_id = version_body["rpaFlowVersionId"]
                checksum = version_body["packageChecksum"]
                version = version_body.get("version") or job["version"]
                print(" uploaded", version_id, checksum)
                val = client.post(
                    f"{ENGINE}/api/v1/flow-versions/{version_id}/validate",
                    headers=HEADERS,
                )
                print(" validate", val.status_code, val.json().get("status"))
                val.raise_for_status()

            pub = client.post(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/publish",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"reason": f"publish {job['flow_id']} {job['version']}"},
            )
            print("publish", job["flow_id"], pub.status_code, pub.text[:300])
            pub.raise_for_status()
            published = pub.json()
            out = {
                "rpaFlowId": job["flow_id"],
                "rpaFlowVersion": published.get("version") or version,
                "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
                "packageChecksum": published.get("packageChecksum") or checksum,
                "status": published.get("status"),
            }
            path = FLOWS / job["flow_id"] / f"_publish_{job['version']}.json"
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
            results.append(out)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
