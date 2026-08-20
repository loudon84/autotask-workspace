import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_check_reply_status_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

validate_input = flow_module.validate_input
resolve_captcha_code = flow_module.resolve_captcha_code


class ValidateInputTests(unittest.TestCase):
    def test_valid_input(self):
        self.assertEqual(validate_input({"po_no": " pojs2607130002 "}), "POJS2607130002")

    def test_rejects_missing_po_no(self):
        with self.assertRaises(RpaBusinessError):
            validate_input({})
        with self.assertRaises(RpaBusinessError):
            validate_input(None)


class CaptchaTests(unittest.TestCase):
    def test_known_captcha(self):
        self.assertEqual(resolve_captcha_code("/assets/code01.png"), "mp3s")


class RunFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_returns_reply_status_without_signing(self):
        adapter = SimpleNamespace(
            login=AsyncMock(),
            open_order_detail=AsyncMock(),
            reply_status=AsyncMock(return_value="已回签"),
        )
        original = flow_module.SupplierPortalReplyStatusAdapter
        flow_module.SupplierPortalReplyStatusAdapter = lambda ctx: adapter
        try:
            result = await flow_module.run(
                SimpleNamespace(
                    input={"po_no": "POJS2607180002"},
                    portal_url="http://example.test/#/login",
                    log=SimpleNamespace(info=AsyncMock()),
                    events=SimpleNamespace(emit=AsyncMock()),
                )
            )
        finally:
            flow_module.SupplierPortalReplyStatusAdapter = original

        self.assertEqual(result["schemaVersion"], "SRM_CHECK_REPLY_STATUS_OUTPUT_V1")
        self.assertEqual(result["poNo"], "POJS2607180002")
        self.assertEqual(result["replyStatus"], "已回签")
        adapter.login.assert_awaited_once()
        adapter.open_order_detail.assert_awaited_once_with("POJS2607180002")
        adapter.reply_status.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
