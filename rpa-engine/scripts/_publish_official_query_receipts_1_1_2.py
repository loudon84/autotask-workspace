"""Build + publish official-portal receipt query 1.1.2.

Official picker for 入库确认时间, filter 对账状态=未提交, export Excel.
Do not bind this version to demo portals (192.168.102.247).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")
FLOW_ID = "rpa_flow_srm_stmt_query_receipts"
VERSION = "1.1.2"
SRC = FLOWS / FLOW_ID / VERSION
DIST = FLOWS / "dist"
ZIP = DIST / f"{FLOW_ID}-{VERSION}.zip"
FILES = ("manifest.json", "selectors.json", "flow.py")


def build() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    ZIP.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            entry = zipfile.ZipInfo(name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 0
            entry.external_attr = 0o100666 << 16
            archive.writestr(entry, (SRC / name).read_bytes())
    print(f"built {ZIP} ({ZIP.stat().st_size} bytes)")


def main() -> None:
    build()
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        with ZIP.open("rb") as fh:
            resp = client.post(
                f"{ENGINE}/api/v1/flows/packages",
                headers=HEADERS,
                files={"package": (ZIP.name, fh, "application/zip")},
                data={
                    "scope": "GLOBAL",
                    "description": f"{FLOW_ID} {VERSION} official picker + 未提交 + xlsx",
                },
            )
        print("upload", resp.status_code, resp.text[:400])
        resp.raise_for_status()
        version_body = resp.json()["version"]
        version_id = version_body["rpaFlowVersionId"]
        checksum = version_body["packageChecksum"]
        val = client.post(
            f"{ENGINE}/api/v1/flow-versions/{version_id}/validate",
            headers=HEADERS,
        )
        print("validate", val.status_code, val.json().get("status"))
        val.raise_for_status()
        pub = client.post(
            f"{ENGINE}/api/v1/flow-versions/{version_id}/publish",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"reason": f"publish {FLOW_ID} {VERSION} official receipt query export"},
        )
        print("publish", pub.status_code, pub.text[:250])
        pub.raise_for_status()
        published = pub.json()
        out = {
            "rpaFlowId": FLOW_ID,
            "rpaFlowVersion": published.get("version") or VERSION,
            "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
            "packageChecksum": published.get("packageChecksum") or checksum,
            "status": published.get("status"),
            "workflowCode": "srm_stmt_query_receipts",
        }
        path = FLOWS / FLOW_ID / f"_publish_{VERSION}.json"
        path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("wrote", path)
        vb = client.post(
            f"{ENGINE}/api/v1/flow-versions/validate-binding",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "rpaFlowId": FLOW_ID,
                "rpaFlowVersion": out["rpaFlowVersion"],
                "workflowCode": "srm_stmt_query_receipts",
            },
        )
        print("validate-binding", vb.status_code, vb.text[:200])
        vb.raise_for_status()
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
