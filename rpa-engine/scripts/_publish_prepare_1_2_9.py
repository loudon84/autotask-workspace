"""Publish prepare 1.2.9 to Engine Registry."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
DIST = FLOWS / "dist"

JOB = {
    "flow_id": "rpa_flow_supplier_portal_prepare_erp_order",
    "version": "1.2.9",
    "zip": DIST / "rpa_flow_supplier_portal_prepare_erp_order-1.2.9.zip",
    "workflow": "srm_prepare_erp_order",
}


def main() -> None:
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        with JOB["zip"].open("rb") as fh:
            resp = client.post(
                f"{ENGINE}/api/v1/flows/packages",
                headers=HEADERS,
                files={"package": (JOB["zip"].name, fh, "application/zip")},
                data={
                    "scope": "GLOBAL",
                    "description": f"{JOB['flow_id']} {JOB['version']}",
                },
            )
        print("upload", JOB["flow_id"], resp.status_code)
        resp.raise_for_status()
        version_body = resp.json()["version"]
        version_id = version_body["rpaFlowVersionId"]
        checksum = version_body["packageChecksum"]
        version = version_body.get("version") or JOB["version"]
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
            json={"reason": f"publish {JOB['flow_id']} {JOB['version']}"},
        )
        print("publish", JOB["flow_id"], pub.status_code, pub.text[:300])
        pub.raise_for_status()
        published = pub.json()
        out = {
            "rpaFlowId": JOB["flow_id"],
            "rpaFlowVersion": published.get("version") or version,
            "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
            "packageChecksum": published.get("packageChecksum") or checksum,
            "status": published.get("status"),
        }
        path = FLOWS / JOB["flow_id"] / f"_publish_{JOB['version']}.json"
        path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("wrote", path)

        vb = client.post(
            f"{ENGINE}/api/v1/flow-versions/validate-binding",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "rpaFlowId": JOB["flow_id"],
                "rpaFlowVersion": out["rpaFlowVersion"],
                "workflowCode": JOB["workflow"],
            },
        )
        print("validate-binding", JOB["workflow"], vb.status_code, vb.text[:250])
        vb.raise_for_status()
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
