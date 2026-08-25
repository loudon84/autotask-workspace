"""Probe SDMS SO attachment response shape. No secrets printed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx

FLOW = Path(
    r"d:\work_space260811\autotask-workspace\rpa-flows"
    r"\rpa_flow_supplier_portal_upload_order_attachment\1.2.0\flow.py"
)
PDF = Path(
    r"d:\work_space260811\autotask-workspace\service\storage\artifacts"
    r"\2be7c618-326d-4a73-91ea-1cfda10f7073\9f307538-f082-4d8e-a49b-d9894634de44"
    r"\a32fa3c2-5484-4e61-8843-2fcd14c332f0\PURCHASE_ORDER.pdf"
)
OUT = Path(r"d:\work_space260811\autotask-workspace\rpa-engine\runtime-cache\_probe_so_attach.json")
BLOB = "http://api.doc.uat.smart-core.com.hk"


def load_flow():
    spec = importlib.util.spec_from_file_location("att_flow", FLOW)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scrub(value):
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if str(key).lower() in {"path", "url", "uploadurl", "access_token", "token"}:
                clean[key] = "<redacted>"
            else:
                clean[key] = scrub(item)
        return clean
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str) and len(value) > 240:
        return value[:240] + "…"
    return value


def main() -> None:
    mod = load_flow()
    content = PDF.read_bytes()
    with httpx.Client(timeout=30.0, trust_env=False, follow_redirects=False) as client:
        token = client.post(
            mod.ERP_TOKEN_URL,
            params={
                "grant_type": "client_credentials",
                "client_id": mod.ERP_CLIENT_ID,
                "client_secret": mod.ERP_CLIENT_SECRET,
            },
            headers={"Accept": "application/json"},
        ).json()["access_token"]
        blob = client.post(
            f"{BLOB}/upload",
            headers={"Accept": "application/json"},
            data={
                "flag": "SDMS_SO1",
                "order_number": "POJS2607240005",
                "username": "S01",
                "filename": "签章合同POJS2607240005",
            },
            files={"file": ("PURCHASE_ORDER.pdf", content, "application/pdf")},
        ).json()
        path = (blob.get("data") or {}).get("path")
        listed = client.get(
            f"{BLOB}/order/SDMS_SO1/POJS2607240005",
            headers={"Accept": "application/json"},
        )
        auth = {"Accept": "application/json", "Authorization": f"bearer {token}"}
        payload = {
            "flag": "SDMS_SO1",
            "custPoNumber": "POJS2607240005",
            "username": "S01",
            "filename": "签章合同POJS2607240005",
            "uploadUrl": path,
        }
        attached = client.post(
            mod.ATTACHMENT_UPLOAD_URL,
            headers=auth,
            data=payload,
            files={"file": ("PURCHASE_ORDER.pdf", content, "application/pdf")},
        )
        listed_body = None
        try:
            listed_body = listed.json()
        except Exception:
            listed_body = {"text": listed.text[:200]}
        result = {
            "blob_code": blob.get("code"),
            "blob_msg": blob.get("msg") or blob.get("message"),
            "list_status": listed.status_code,
            "list": scrub(listed_body),
            "attach_status": attached.status_code,
            "attach": scrub(attached.json()),
        }
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", OUT)
        print("blob", result["blob_code"], result["blob_msg"])
        print("list", result["list_status"])
        print("attach", result["attach_status"], result["attach"].get("code"), result["attach"].get("message"))


if __name__ == "__main__":
    main()
