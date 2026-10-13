import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "srm_sign_order_flow_1_1_0",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

validate_input = flow_module.validate_input
parse_order_lines = flow_module.parse_order_lines
sign_result = flow_module.sign_result
run = flow_module.run


class ValidateInputTests(unittest.TestCase):
    def test_requires_order_lines(self):
        with self.assertRaises(RpaBusinessError) as ctx:
            validate_input({"po_no": "POJS2607130002"})
        self.assertEqual(ctx.exception.code, "FLOW_INPUT_INVALID")

    def test_parses_order_lines(self):
        po_no, lines = validate_input(
            {
                "po_no": " pojs2610120010 ",
                "order_lines": [
                    {"line_number": "10", "expected_delivery_date": "2026-11-28"},
                ],
            }
        )
        self.assertEqual(po_no, "POJS2610120010")
        self.assertEqual(
            lines,
            [{"lineNo": "10", "expectedDeliveryDate": "2026-11-28"}],
        )

    def test_rejects_bad_date(self):
        with self.assertRaises(RpaBusinessError):
            parse_order_lines(
                {
                    "order_lines": [
                        {"line_number": "10", "expected_delivery_date": "11/28/2026"},
                    ]
                }
            )


class SignResultTests(unittest.TestCase):
    def test_dry_run_payload(self):
        payload = sign_result(
            dry_run=True,
            po_no="POJS2610120010",
            line_count=1,
            reply_status="待签章",
        )
        self.assertTrue(payload["dryRun"])
        self.assertFalse(payload["signed"])
        self.assertTrue(payload["filledSupplierDates"])


class DryRunRunTests(unittest.IsolatedAsyncioTestCase):
    async def test_dry_run_skips_sign_click(self):
        adapter = MagicMock()
        adapter.login = AsyncMock()
        adapter.open_order_detail = AsyncMock()
        adapter.reply_status = AsyncMock(return_value="待签章")
        adapter.fill_supplier_delivery_dates = AsyncMock()
        sign_button = MagicMock()
        adapter.ensure_signable = AsyncMock(return_value=sign_button)
        adapter.sign_and_verify = AsyncMock()
        original_adapter = flow_module.SupplierPortalSignAdapter
        original_guard = flow_module.install_write_guard
        flow_module.SupplierPortalSignAdapter = MagicMock(return_value=adapter)
        guard = AsyncMock()
        flow_module.install_write_guard = guard
        try:
            ctx = SimpleNamespace(
                portal_url="https://supplier.tiandy.com",
                input={
                    "po_no": "POJS2610120010",
                    "order_lines": [
                        {"line_number": "10", "expected_delivery_date": "2026-11-28"},
                    ],
                },
                config={"dryRun": True},
                page=MagicMock(),
                selectors={},
                log=SimpleNamespace(info=AsyncMock()),
                events=SimpleNamespace(emit=AsyncMock()),
                artifacts=SimpleNamespace(screenshot=AsyncMock()),
            )
            result = await run(ctx)
        finally:
            flow_module.SupplierPortalSignAdapter = original_adapter
            flow_module.install_write_guard = original_guard

        self.assertTrue(result["dryRun"])
        self.assertFalse(result["signed"])
        adapter.fill_supplier_delivery_dates.assert_awaited()
        guard.assert_awaited()
        adapter.ensure_signable.assert_awaited()
        adapter.sign_and_verify.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
