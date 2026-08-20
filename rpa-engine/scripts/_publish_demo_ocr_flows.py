"""Build + publish demo-portal OCR login Flow packages. Official portal is not bound here."""
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
JOBS = [
    {"flow_id": "rpa_flow_srm_check_reply_status", "workflow": "srm_check_reply_status", "version": "1.0.1"},
    {"flow_id": "rpa_flow_srm_fill_line_delivery_date", "workflow": "srm_fill_line_delivery_date", "version": "1.0.3"},
    {"flow_id": "rpa_flow_supplier_portal_prepare_erp_order", "workflow": "srm_prepare_erp_order", "version": "1.2.11"},
    {"flow_id": "rpa_flow_srm_sign_order", "workflow": "srm_sign_order", "version": "1.0.3"},
    {"flow_id": "rpa_flow_supplier_portal_upload_order_attachment", "workflow": "srm_upload_order_attachment", "version": "1.2.5"},
    {"flow_id": "rpa_flow_srm_stmt_query_receipts", "workflow": "srm_stmt_query_receipts", "version": "1.0.4"},
    {"flow_id": "rpa_flow_srm_stmt_generate", "workflow": "srm_stmt_generate", "version": "1.0.7"},
    {"flow_id": "rpa_flow_srm_stmt_upload_invoice", "workflow": "srm_stmt_upload_invoice", "version": "1.0.6"},
    {"flow_id": "rpa_flow_srm_stmt_submit_review", "workflow": "srm_stmt_submit_review", "version": "1.0.7"},
]


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


def main() -> None:
    results: list[dict] = []
    with httpx.Client(timeout=60.0, trust_env=False) as client:
        for job in JOBS:
            zip_path = build(job["flow_id"], job["version"])
            with zip_path.open("rb") as fh:
                resp = client.post(
                    f"{ENGINE}/api/v1/flows/packages",
                    headers=HEADERS,
                    files={"package": (zip_path.name, fh, "application/zip")},
                    data={
                        "scope": "GLOBAL",
                        "description": f"{job['flow_id']} {job['version']} demo OCR",
                    },
                )
            print("upload", job["flow_id"], resp.status_code, resp.text[:400])
            resp.raise_for_status()
            version_body = resp.json()["version"]
            version_id = version_body["rpaFlowVersionId"]
            checksum = version_body["packageChecksum"]
            val = client.post(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/validate",
                headers=HEADERS,
            )
            print(" validate", val.status_code, val.json().get("status"))
            val.raise_for_status()
            pub = client.post(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/publish",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"reason": f"publish {job['flow_id']} {job['version']} demo OCR"},
            )
            print("publish", job["flow_id"], pub.status_code, pub.text[:250])
            pub.raise_for_status()
            published = pub.json()
            out = {
                "rpaFlowId": job["flow_id"],
                "rpaFlowVersion": published.get("version") or job["version"],
                "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
                "packageChecksum": published.get("packageChecksum") or checksum,
                "status": published.get("status"),
                "workflowCode": job["workflow"],
            }
            path = FLOWS / job["flow_id"] / f"_publish_{job['version']}.json"
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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

    combined = FLOWS / "_publish_demo_ocr.json"
    combined.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", combined)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
