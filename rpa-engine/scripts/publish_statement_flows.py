"""Build, upload, validate and publish statement Flow packages via curl.exe."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "rpa-engine"
FLOWS = ROOT / "rpa-flows"
ENGINE_URL = "http://127.0.0.1:4610"
PACKAGES = [
    ("rpa_flow_srm_stmt_query_receipts", "1.0.0"),
    ("rpa_flow_srm_stmt_generate", "1.0.0"),
    ("rpa_flow_srm_stmt_upload_invoice", "1.0.0"),
    ("rpa_flow_srm_stmt_submit_review", "1.0.0"),
]


def manifest_version(flow_id: str, folder: str) -> str:
    path = FLOWS / flow_id / folder / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))["version"]


def run_curl(args: list[str]) -> dict:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    stdout = completed.stdout or ""
    if completed.returncode != 0:
        print(stdout[-1000:])
        print((completed.stderr or "")[-1000:])
        raise RuntimeError(f"curl failed: {args[:8]}")
    body, _, code = stdout.rpartition("\n")
    if code.strip() and not code.strip().isdigit():
        body = stdout
        code = "200"
    status = int(code.strip() or "0")
    if status >= 400:
        print(body[-1000:])
        raise RuntimeError(f"HTTP {status} for {args[6] if len(args) > 6 else args}")
    return json.loads(body or "{}")


def build(flow_id: str, version: str) -> Path:
    flow_dir = FLOWS / flow_id / version
    zip_path = FLOWS / "dist" / f"{flow_id}-{version}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ENGINE / "src")
    subprocess.check_call(
        [
            str(ENGINE / ".venv" / "Scripts" / "python.exe"),
            str(FLOWS / "scripts" / "build_flow_package.py"),
            "--flow-dir",
            str(flow_dir),
            "--output",
            str(zip_path),
        ],
        cwd=str(ENGINE),
        env=env,
    )
    return zip_path


def publish_one(flow_id: str, version: str, zip_path: Path) -> dict:
    upload = run_curl(
        [
            "curl.exe",
            "-sS",
            "-w",
            "\n%{http_code}",
            "-X",
            "POST",
            f"{ENGINE_URL}/api/v1/flows/packages",
            "-H",
            "X-Actor-Id: flow-registry-operator",
            "-F",
            f"package=@{zip_path};type=application/zip",
            "-F",
            "scope=GLOBAL",
            "-F",
            f"description={flow_id}",
            "-F",
            'labels=["srm","statement"]',
        ]
    )
    version_body = upload["version"]
    version_id = version_body["rpaFlowVersionId"]
    checksum = version_body["packageChecksum"]
    print("upload", flow_id, version_id, checksum)
    validate = run_curl(
        [
            "curl.exe",
            "-sS",
            "-w",
            "\n%{http_code}",
            "-X",
            "POST",
            f"{ENGINE_URL}/api/v1/flow-versions/{version_id}/validate",
            "-H",
            "X-Actor-Id: flow-registry-operator",
        ]
    )
    print("validate", flow_id, validate.get("status"))
    published = run_curl(
        [
            "curl.exe",
            "-sS",
            "-w",
            "\n%{http_code}",
            "-X",
            "POST",
            f"{ENGINE_URL}/api/v1/flow-versions/{version_id}/publish",
            "-H",
            "X-Actor-Id: flow-registry-operator",
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"reason": f"publish {flow_id} {version}"}),
        ]
    )
    print("publish", flow_id, published.get("status"))
    return {
        "rpaFlowId": flow_id,
        "rpaFlowVersion": version_body.get("version") or version,
        "rpaFlowVersionId": published.get("rpaFlowVersionId") or version_id,
        "packageChecksum": published.get("packageChecksum") or checksum,
        "status": published.get("status"),
    }


def main() -> int:
    wanted = set(sys.argv[1:])
    results = []
    for flow_id, folder in PACKAGES:
        if wanted and flow_id not in wanted:
            continue
        zip_path = build(flow_id, folder)
        results.append(publish_one(flow_id, manifest_version(flow_id, folder), zip_path))
    if not results:
        raise SystemExit(f"no packages matched {sorted(wanted)}")
    out = ENGINE / "runtime-cache" / "statement-flow-publish.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = {}
    if out.exists():
        for item in json.loads(out.read_text(encoding="utf-8")):
            merged[item["rpaFlowId"]] = item
    for item in results:
        merged[item["rpaFlowId"]] = item
    out.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
