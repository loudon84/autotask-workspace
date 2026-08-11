import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from playwright.async_api import async_playwright

from probe import PORTAL_URL, read_env


ROOT = Path(__file__).resolve().parents[2]
FLOW_DIR = (
    ROOT
    / "rpa_flow_supplier_portal_update_delivery_dates"
    / "1.0.0"
)
CONFIG = Path(__file__).with_name("local-runner-config.json")
SCREENSHOT = Path(__file__).with_name("dry-run-filled.png")
SIGNED_PO_NO = "POJS2604230016"


class Events:
    async def emit(self, *_args, **_kwargs):
        return None


class Artifacts:
    async def screenshot(self, *_args, **_kwargs):
        return None


async def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "delivery_date_flow_dry_run",
        FLOW_DIR / "flow.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    selectors = json.loads(
        (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
    )
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    env = read_env()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel="chrome",
            headless=True,
        )
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        ctx = SimpleNamespace(
            page=page,
            portal_url=PORTAL_URL,
            credentials={
                "username": env["MOCK_SRM_USERNAME"],
                "password": env["MOCK_SRM_PASSWORD"],
            },
            selectors=selectors,
            events=Events(),
            artifacts=Artifacts(),
        )
        adapter = module.SupplierPortalDeliveryDateAdapter(ctx)
        po_no, requested_lines = module.validate_input(config["input"])
        await adapter.login()
        await adapter.open_order_detail(po_no)
        before = await adapter.collect_order_lines()
        resolved = module.reconcile_order_lines(before, requested_lines)
        await adapter.ensure_editable(resolved)
        await adapter.fill_and_verify(resolved)
        await adapter.wait_for_detail_stable(resolved)
        await page.screenshot(path=str(SCREENSHOT), full_page=True)

        await page.reload(wait_until="domcontentloaded")
        await page.locator(
            selectors["detail_po_number"].replace("{po_no}", po_no)
        ).wait_for(state="visible", timeout=15_000)
        after = await adapter.collect_order_lines()
        unchanged = {
            line["lineNo"]: line["currentExpectedDate"] for line in before
        } == {
            line["lineNo"]: line["currentExpectedDate"] for line in after
        }
        await adapter.open_order_detail(SIGNED_PO_NO)
        signed_lines = await adapter.collect_order_lines()
        signed_status = await adapter.reply_status()
        sign_enabled = await page.locator(selectors["sign"]).is_enabled()
        print(
            json.dumps(
                {
                    "poNo": po_no,
                    "lineCount": len(resolved),
                    "lineNumbers": [line["lineNo"] for line in resolved],
                    "materialNumbers": [
                        line["materialNo"] for line in resolved
                    ],
                    "filledLocally": True,
                    "saveClicked": False,
                    "serverValuesUnchangedAfterReload": unchanged,
                    "signedReadOnlyProbe": {
                        "poNo": SIGNED_PO_NO,
                        "replyStatus": signed_status,
                        "lineCount": len(signed_lines),
                        "signEnabled": sign_enabled,
                    },
                },
                ensure_ascii=False,
            )
        )
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
