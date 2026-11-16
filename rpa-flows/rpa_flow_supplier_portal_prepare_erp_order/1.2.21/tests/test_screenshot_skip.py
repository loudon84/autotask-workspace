import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


FLOW_DIR = Path(__file__).resolve().parents[1]
FLOW_SPEC = importlib.util.spec_from_file_location(
    "supplier_portal_prepare_erp_order_flow_1_2_21_screenshot",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(FLOW_SPEC)
sys.modules[FLOW_SPEC.name] = flow_module
FLOW_SPEC.loader.exec_module(flow_module)


class _Log:
    def __init__(self):
        self.messages = []

    async def info(self, message, payload=None):
        self.messages.append((message, payload))


class _Artifacts:
    def __init__(self, error):
        self.error = error
        self.calls = []

    async def screenshot(self, name, *, full_page=True, step_id=None):
        self.calls.append({"name": name, "full_page": full_page, "step_id": step_id})
        if self.error is not None:
            raise self.error


class ScreenshotSkipTest(unittest.TestCase):
    def test_timeout_does_not_abort_prepare(self):
        artifacts = _Artifacts(TimeoutError("screenshot"))
        log = _Log()
        ctx = SimpleNamespace(artifacts=artifacts, log=log)
        asyncio.run(flow_module._capture_prepare_screenshot(ctx))
        self.assertEqual(artifacts.calls[0]["full_page"], False)
        self.assertIn("Skipped ERP draft evidence screenshot", log.messages[0][0])
        self.assertEqual(log.messages[0][1]["error"], "TimeoutError")

    def test_viewport_shot_is_recorded(self):
        artifacts = _Artifacts(None)
        log = _Log()
        ctx = SimpleNamespace(artifacts=artifacts, log=log)
        asyncio.run(flow_module._capture_prepare_screenshot(ctx))
        self.assertEqual(log.messages, [])
        self.assertEqual(
            artifacts.calls[0]["name"], "supplier-portal-erp-draft-prepared"
        )


if __name__ == "__main__":
    unittest.main()
