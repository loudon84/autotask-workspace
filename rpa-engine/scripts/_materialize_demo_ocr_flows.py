# -*- coding: utf-8 -*-
"""Copy demo-portal login Flows, replace login with OCR helper, bump versions.

Does not publish or bind. Does not touch official 1.1.x packages.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import httpx

ENGINE = "http://127.0.0.1:4610"
HEADERS = {"X-Actor-Id": "flow-registry-operator"}
FLOWS = Path(r"d:\work_space260811\autotask-workspace\rpa-flows")

JOBS = [
    {
        "flow_id": "rpa_flow_srm_check_reply_status",
        "workflow": "srm_check_reply_status",
        "src": "1.0.0",
        "dst": "1.0.1",
        "login": "method",
        "prefer_bound": None,
    },
    {
        "flow_id": "rpa_flow_srm_fill_line_delivery_date",
        "workflow": "srm_fill_line_delivery_date",
        "src": "1.0.2",
        "dst": "1.0.3",
        "login": "method",
        "prefer_bound": None,
    },
    {
        "flow_id": "rpa_flow_supplier_portal_prepare_erp_order",
        "workflow": "srm_prepare_erp_order",
        "src": "1.2.10",
        "dst": "1.2.11",
        "login": "method",
        "prefer_bound": None,
    },
    {
        "flow_id": "rpa_flow_srm_sign_order",
        "workflow": "srm_sign_order",
        "src": "1.0.2",
        "dst": "1.0.3",
        "login": "method",
        "prefer_bound": None,
    },
    {
        "flow_id": "rpa_flow_supplier_portal_upload_order_attachment",
        "workflow": "srm_upload_order_attachment",
        "src": "1.2.4",
        "dst": "1.2.5",
        "login": "method",
        "prefer_bound": None,
    },
    {
        "flow_id": "rpa_flow_srm_stmt_query_receipts",
        "workflow": "srm_stmt_query_receipts",
        "src": "1.0.0",
        "dst": "1.0.4",
        "login": "method",
        "prefer_bound": "1.0.3",
    },
    {
        "flow_id": "rpa_flow_srm_stmt_generate",
        "workflow": "srm_stmt_generate",
        "src": "1.0.0",
        "dst": "1.0.7",
        "login": "method",
        "prefer_bound": "1.0.6",
    },
    {
        "flow_id": "rpa_flow_srm_stmt_upload_invoice",
        "workflow": "srm_stmt_upload_invoice",
        "src": "1.0.0",
        "dst": "1.0.6",
        "login": "func",
        "prefer_bound": "1.0.5",
    },
    {
        "flow_id": "rpa_flow_srm_stmt_submit_review",
        "workflow": "srm_stmt_submit_review",
        "src": "1.0.0",
        "dst": "1.0.7",
        "login": "func",
        "prefer_bound": "1.0.6",
    },
]

LOGIN_METHOD = """    async def login(self):
        await login_official_srm(self.ctx, selector=self.selector)
"""

LOGIN_FUNC = """async def _login(ctx):
    selectors = ctx.selectors if isinstance(ctx.selectors, Mapping) else {}

    def selector(name, **values):
        value = selectors.get(name)
        if not isinstance(value, str) or not value:
            raise RpaFatalError("FLOW_SELECTOR_MISSING", f"missing selector: {name}")
        for key, replacement in values.items():
            value = value.replace(f"{{{key}}}", str(replacement))
        return value

    await login_official_srm(ctx, selector=selector)
"""

OCR_NOTE = """
## {version} 变更

- 登录验证码改为本机 `ddddocr` 读图，不再用文件名对照。
- 最多 3 次；失败抛可重试错误，不停成待人工。
- **适用门户：演示门户**（`http://192.168.102.247:3000`）。不能绑正式门户。

"""


def replace_def_block(text: str, def_prefix: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    header_idx = next((i for i, line in enumerate(lines) if line.startswith(def_prefix)), None)
    if header_idx is None:
        raise SystemExit(f"missing {def_prefix!r}")
    header_indent = len(lines[header_idx]) - len(lines[header_idx].lstrip(" "))
    end = header_idx + 1
    while end < len(lines):
        raw = lines[end]
        if raw.strip() == "":
            end += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= header_indent:
            break
        end += 1
    repl = replacement if replacement.endswith("\n") else replacement + "\n"
    if not repl.endswith("\n\n"):
        repl += "\n"
    return "".join(lines[:header_idx]) + repl + "".join(lines[end:])


def ensure_import(text: str) -> str:
    if re.search(r"\blogin_official_srm\b", text):
        return text
    match = re.search(r"from nodeskclaw_rpa_engine\.runtime import \(\n", text)
    if not match:
        raise SystemExit("runtime import block not found")
    return text[: match.end()] + "    login_official_srm,\n" + text[match.end() :]


def bump_manifest(path: Path, dst: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = dst
    name = str(data.get("name") or "")
    if "Demo OCR" not in name:
        data["name"] = f"{name} (Demo OCR)" if name else f"Demo OCR {dst}"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bump_readme(path: Path, src: str, dst: str) -> None:
    note = OCR_NOTE.format(version=dst).lstrip("\n")
    if not path.exists():
        path.write_text(
            f"# {path.parent.parent.name} {dst}\n\n{note}",
            encoding="utf-8",
        )
        return
    text = path.read_text(encoding="utf-8")
    text = text.replace(src, dst)
    if f"## {dst} 变更" not in text:
        parts = text.split("\n", 1)
        if len(parts) == 2:
            text = parts[0] + "\n\n" + note + parts[1].lstrip("\n")
        else:
            text = text + "\n" + note
    path.write_text(text, encoding="utf-8")


def patch_test_module_names(tests_dir: Path, src: str, dst: str) -> None:
    if not tests_dir.exists():
        return
    src_token = src.replace(".", "_")
    dst_token = dst.replace(".", "_")
    for path in tests_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace(src_token, dst_token)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def patch_prepare_login_test(path: Path) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    old = '''                selectors={
                    "login_ready": "login-ready",
                    "login_success": "login-success",
                },
            )
        )

        await adapter.login()

        self.assertEqual(
            timeline,
            [
                ("goto", "http://portal.test/", "domcontentloaded"),
                ("wait", "login-ready", "visible", 10000),
                ("visible", "login-success"),
            ],
        )'''
    new = '''                selectors={
                    "login_success": "login-success",
                    "captcha_image": "captcha-image",
                },
            )
        )

        await adapter.login()

        self.assertEqual(
            timeline,
            [
                ("visible", "login-success"),
                ("visible", "captcha-image"),
            ],
        )'''
    if old not in text:
        raise SystemExit(f"prepare login reuse test block not found: {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def download_bound_package(flow_id: str, version: str, dest: Path) -> bool:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, trust_env=False) as client:
            listed = client.get(
                f"{ENGINE}/api/v1/flows/{flow_id}/versions",
                headers=HEADERS,
                params={"scope": "GLOBAL"},
            )
            if listed.status_code != 200:
                print(f" list-versions {flow_id} -> {listed.status_code}")
                return False
            items = listed.json().get("items") or []
            match = next((item for item in items if item.get("version") == version), None)
            if match is None:
                print(f" bound version {flow_id}@{version} not in registry")
                return False
            version_id = match["rpaFlowVersionId"]
            pkg = client.get(
                f"{ENGINE}/api/v1/flow-versions/{version_id}/package",
                headers=HEADERS,
            )
            if pkg.status_code != 200:
                print(f" download {flow_id}@{version} -> {pkg.status_code}")
                return False
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(pkg.content)) as archive:
                archive.extractall(dest)
            print(f" downloaded {flow_id}@{version} -> {dest}")
            return True
    except Exception as exc:
        print(f" download {flow_id}@{version} failed: {exc}")
        return False


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".ready"),
    )


def patch_flow(job: dict, dest: Path) -> None:
    flow_path = dest / "flow.py"
    text = ensure_import(flow_path.read_text(encoding="utf-8"))
    if job["login"] == "method":
        text = replace_def_block(text, "    async def login(self):", LOGIN_METHOD)
    elif job["login"] == "func":
        text = replace_def_block(text, "async def _login(ctx):", LOGIN_FUNC)
    else:
        raise SystemExit(f"unknown login kind: {job['login']}")
    flow_path.write_text(text, encoding="utf-8")
    bump_manifest(dest / "manifest.json", job["dst"])
    bump_readme(dest / "README.md", job["src"], job["dst"])
    patch_test_module_names(dest / "tests", job["src"], job["dst"])
    if job["flow_id"] == "rpa_flow_supplier_portal_prepare_erp_order":
        patch_prepare_login_test(dest / "tests" / "test_flow.py")


def main() -> None:
    for job in JOBS:
        dest = FLOWS / job["flow_id"] / job["dst"]
        src_used = job["src"]
        if job["prefer_bound"]:
            tmp = FLOWS / job["flow_id"] / f"_tmp_{job['prefer_bound']}"
            if download_bound_package(job["flow_id"], job["prefer_bound"], tmp):
                copy_tree(tmp, dest)
                shutil.rmtree(tmp, ignore_errors=True)
                src_used = job["prefer_bound"]
            else:
                shutil.rmtree(tmp, ignore_errors=True)
                copy_tree(FLOWS / job["flow_id"] / job["src"], dest)
        else:
            copy_tree(FLOWS / job["flow_id"] / job["src"], dest)
        tree_tests = FLOWS / job["flow_id"] / job["src"] / "tests"
        if not (dest / "tests").exists() and tree_tests.exists():
            shutil.copytree(
                tree_tests,
                dest / "tests",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        job_copy = dict(job)
        job_copy["src"] = src_used
        patch_flow(job_copy, dest)
        print(f"materialized {job['flow_id']} {src_used} -> {job['dst']}")


if __name__ == "__main__":
    main()
