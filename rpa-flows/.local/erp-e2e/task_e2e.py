from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


ENGINE_ENV = Path(r"D:\AutoTask-Workspace\nodeskclaw-rpa-engine\.env")
AUTH_URL = "http://192.168.102.247:4510/api/v1/auth/account-login"
STATE_PATH = Path(__file__).with_name("state.json")

FLOW_ID = "rpa_flow_supplier_portal_prepare_erp_order"
FLOW_VERSION = "1.1.0"
FLOW_VERSION_ID = "89ca0ffe-cd87-4f00-9f6f-c16974aa437f"
FLOW_CHECKSUM = (
    "sha256:ae0b4a5a7ef585cc4986ed74580e69576b87aed38ed97f3ca9897583a01dd47b"
)
WORKFLOW_CODE = "srm_prepare_erp_order"
TEMPLATE_VERSION = "1.0.0"
PORTAL_ID = "b182630d-5023-45c3-ac9c-6b022765b7e1"
PO_NO = "POJS2606030010"


class E2EError(RuntimeError):
    pass


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[name.strip()] = value
    return values


def normalize_checksum(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text.removeprefix("sha256:")


def unwrap(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError as exc:
        raise E2EError(f"HTTP {response.status_code}: non-JSON response") from exc
    if not response.is_success:
        error = payload.get("error", payload) if isinstance(payload, dict) else {}
        code = (
            error.get("code", "HTTP_ERROR") if isinstance(error, dict) else "HTTP_ERROR"
        )
        message = (
            error.get("message", "Request failed")
            if isinstance(error, dict)
            else "Request failed"
        )
        raise E2EError(f"HTTP {response.status_code}: {code}: {message}")
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return [item for item in value["items"] if isinstance(item, dict)]
    return []


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise E2EError("Local state file is invalid")
    return value


def save_state(value: dict[str, Any]) -> None:
    STATE_PATH.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class TaskClient:
    def __init__(self) -> None:
        env = read_dotenv(ENGINE_ENV)
        account = env.get("TASK_CLIENT_ID", "")
        password = env.get("TASK_CLIENT_SECRET", "")
        task_base = env.get("TASK_API_BASE_URL", "").rstrip("/")
        if not account or not password or not task_base:
            raise E2EError("Task service account or API base URL is not configured")
        self.client = httpx.Client(timeout=20.0, trust_env=False)
        login = unwrap(
            self.client.post(
                AUTH_URL,
                json={"account": account, "password": password},
            )
        )
        token = login.get("access_token") if isinstance(login, dict) else None
        token_type = (
            login.get("token_type", "bearer") if isinstance(login, dict) else ""
        )
        if not isinstance(token, str) or not token:
            raise E2EError("Task login response did not contain an access token")
        self.task_base = task_base
        self.client.headers["Authorization"] = f"{token_type} {token}"

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        response = self.client.request(
            method,
            f"{self.task_base}{path}",
            params=params,
            json=body,
        )
        return unwrap(response)


def assert_queue_empty(client: TaskClient) -> None:
    queued = items(
        client.request(
            "GET",
            "/tasks",
            params={"status": "QUEUED", "page": 1, "pageSize": 100},
        )
    )
    if queued:
        identifiers = ", ".join(str(item.get("id", "")) for item in queued)
        raise E2EError(f"Unrelated QUEUED tasks exist: {identifiers}")


def get_portal(client: TaskClient) -> dict[str, Any]:
    portal = client.request("GET", f"/portal-accounts/{PORTAL_ID}")
    if not isinstance(portal, dict):
        raise E2EError("Portal response is invalid")
    if portal.get("status") != "ENABLED":
        raise E2EError("Portal is not enabled")
    portal_url = portal.get("portalUrl")
    if not isinstance(portal_url, str) or not portal_url.startswith(
        ("http://", "https://")
    ):
        raise E2EError("Portal URL is invalid")
    return portal


def expected_input_schema() -> list[dict[str, Any]]:
    return [{"name": "po_no", "type": "string", "required": True}]


def ensure_template(client: TaskClient) -> dict[str, Any]:
    matches = [
        item
        for item in items(client.request("GET", "/workflow-templates"))
        if item.get("code") == WORKFLOW_CODE
    ]
    if len(matches) > 1:
        raise E2EError("Multiple workflow templates use srm_prepare_erp_order")
    if not matches:
        template = client.request(
            "POST",
            "/workflow-templates",
            body={
                "name": "供应商门户 ERP 订单推送",
                "code": WORKFLOW_CODE,
                "description": "ERP 订单推送 Flow 1.1.0 受控闭环测试",
                "entity_type": "CUSTOMER",
                "category": "procurement",
                "status": "DRAFT",
                "version": TEMPLATE_VERSION,
                "input_schema": expected_input_schema(),
                "business_steps": [],
            },
        )
    else:
        template = matches[0]
        if (
            template.get("version") != TEMPLATE_VERSION
            or template.get("entityType") != "CUSTOMER"
            or template.get("inputSchema") != expected_input_schema()
        ):
            raise E2EError(
                "Existing workflow template conflicts with the test contract"
            )
    if template.get("status") == "DRAFT":
        template = client.request(
            "POST",
            f"/workflow-templates/{template['id']}/enable",
        )
    if template.get("status") != "ENABLED":
        raise E2EError("Workflow template is not enabled")
    return template


def binding_matches(
    binding: dict[str, Any],
    *,
    template_id: str,
    portal_url: str,
) -> bool:
    config = binding.get("config")
    browser = config.get("browserSession") if isinstance(config, dict) else None
    return (
        binding.get("portalAccountId") == PORTAL_ID
        and binding.get("workflowTemplateId") == template_id
        and binding.get("workflowTemplateVersion") == TEMPLATE_VERSION
        and binding.get("rpaFlowId") == FLOW_ID
        and binding.get("rpaFlowVersion") == FLOW_VERSION
        and binding.get("rpaFlowVersionId") == FLOW_VERSION_ID
        and normalize_checksum(binding.get("flowChecksumSnapshot"))
        == normalize_checksum(FLOW_CHECKSUM)
        and binding.get("status") == "ENABLED"
        and isinstance(config, dict)
        and config.get("portalUrl") == portal_url
        and isinstance(browser, dict)
        and browser.get("mode") == "MANAGED"
        and browser.get("headless") is True
        and browser.get("channel") == "chrome"
        and browser.get("closePolicy") == "CLOSE_ON_FINISH"
    )


def ensure_binding(
    client: TaskClient,
    *,
    template: dict[str, Any],
    portal: dict[str, Any],
) -> dict[str, Any]:
    all_bindings = items(client.request("GET", "/workflow-bindings"))
    matches = [item for item in all_bindings if item.get("rpaFlowId") == FLOW_ID]
    if len(matches) > 1:
        raise E2EError("Multiple bindings already reference the ERP Flow")
    if matches:
        binding = matches[0]
        if not binding_matches(
            binding,
            template_id=str(template["id"]),
            portal_url=str(portal["portalUrl"]),
        ):
            raise E2EError("Existing ERP Flow binding conflicts with the test contract")
        return binding
    binding = client.request(
        "POST",
        "/workflow-bindings",
        body={
            "portal_account_id": PORTAL_ID,
            "workflow_template_id": template["id"],
            "workflow_template_version": TEMPLATE_VERSION,
            "rpa_engine_type": "PLAYWRIGHT_CDP",
            "rpa_flow_id": FLOW_ID,
            "rpa_flow_version": FLOW_VERSION,
            "status": "ENABLED",
            "config": {
                "portalUrl": portal["portalUrl"],
                "browserSession": {
                    "mode": "MANAGED",
                    "headless": True,
                    "channel": "chrome",
                    "profileRef": None,
                    "cdpEndpointRef": None,
                    "closePolicy": "CLOSE_ON_FINISH",
                },
            },
        },
    )
    if not binding_matches(
        binding,
        template_id=str(template["id"]),
        portal_url=str(portal["portalUrl"]),
    ):
        raise E2EError("Created binding does not contain the exact Flow snapshot")
    return binding


def ensure_assets(client: TaskClient) -> None:
    assert_queue_empty(client)
    portal = get_portal(client)
    template = ensure_template(client)
    binding = ensure_binding(client, template=template, portal=portal)
    state = load_state()
    state.update(
        {
            "flow_version_id": FLOW_VERSION_ID,
            "flow_checksum": FLOW_CHECKSUM,
            "portal_id": portal["id"],
            "portal_url": portal["portalUrl"],
            "template_id": template["id"],
            "binding_id": binding["id"],
        }
    )
    save_state(state)
    print(
        json.dumps(
            {
                "queue_empty": True,
                "portal_id": portal["id"],
                "portal_status": portal["status"],
                "template_id": template["id"],
                "template_status": template["status"],
                "binding_id": binding["id"],
                "binding_status": binding["status"],
                "flow_version_id": binding["rpaFlowVersionId"],
                "flow_checksum": binding["flowChecksumSnapshot"],
            },
            ensure_ascii=False,
        )
    )


def create_and_start(client: TaskClient) -> None:
    state = load_state()
    if state.get("task_id"):
        raise E2EError("A test Task has already been created; refusing a second start")
    assert_queue_empty(client)
    portal = get_portal(client)
    task = client.request(
        "POST",
        "/tasks",
        body={
            "title": f"ERP 订单推送闭环 {PO_NO}",
            "task_type": WORKFLOW_CODE,
            "portal_account_id": PORTAL_ID,
            "workflow_binding_id": state["binding_id"],
            "entity_type": portal["entityType"],
            "erp_entity_code": portal["erpEntityCode"],
            "erp_entity_name": portal["erpEntityName"],
            "priority": "NORMAL",
            "input": {"po_no": PO_NO},
        },
    )
    state["task_id"] = task["id"]
    save_state(state)
    started = client.request("POST", f"/tasks/{task['id']}/start")
    print(
        json.dumps(
            {
                "task_id": started["id"],
                "task_status": started["status"],
                "po_no": started["input"].get("po_no"),
            },
            ensure_ascii=False,
        )
    )


def snapshot(client: TaskClient) -> None:
    state = load_state()
    task_id = state.get("task_id")
    if not task_id:
        raise E2EError("No test Task has been created")
    task = client.request("GET", f"/tasks/{task_id}")
    runs = items(client.request("GET", f"/tasks/{task_id}/runs"))
    result: dict[str, Any] = {
        "task_id": task_id,
        "task_status": task.get("status"),
        "task_current_step": task.get("currentStep"),
        "task_progress": task.get("progress"),
        "runs": [],
    }
    for run in runs:
        run_id = str(run["id"])
        events = items(client.request("GET", f"/runs/{run_id}/events"))
        artifacts = items(client.request("GET", f"/tasks/{task_id}/artifacts"))
        result["runs"].append(
            {
                "run_id": run_id,
                "status": run.get("status"),
                "worker_id": run.get("rpaWorkerId"),
                "lease_id": run.get("leaseId"),
                "current_step_id": run.get("currentStepId"),
                "error_code": run.get("errorCode"),
                "error_message": run.get("errorMessage"),
                "started_at": run.get("startedAt"),
                "ended_at": run.get("endedAt"),
                "events": [
                    {
                        "type": event.get("type"),
                        "level": event.get("level"),
                        "message": event.get("message"),
                        "payload": event.get("payload"),
                        "created_at": event.get("createdAt"),
                    }
                    for event in events
                ],
                "artifacts": [
                    {
                        "id": artifact.get("id"),
                        "type": artifact.get("type"),
                        "name": artifact.get("name"),
                        "size": artifact.get("size"),
                        "mime_type": artifact.get("mimeType"),
                    }
                    for artifact in artifacts
                    if artifact.get("runId") in {None, run_id}
                ],
            }
        )
    print(json.dumps(result, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("ensure-assets", "create-and-start", "snapshot"),
    )
    args = parser.parse_args()
    client: TaskClient | None = None
    try:
        client = TaskClient()
        if args.command == "ensure-assets":
            ensure_assets(client)
        elif args.command == "create-and-start":
            create_and_start(client)
        else:
            snapshot(client)
        return 0
    except (E2EError, KeyError, httpx.RequestError) as exc:
        print(f"E2E_ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
