import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

from nodeskclaw_rpa_engine.runtime import (
    RpaBusinessError,
    RpaHumanRequiredError,
    RpaRetryableError,
)

FLOW_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "supplier_portal_update_delivery_dates_flow",
    FLOW_DIR / "flow.py",
)
flow_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow_module
SPEC.loader.exec_module(flow_module)

reconcile_order_lines = flow_module.reconcile_order_lines
resolve_captcha_code = flow_module.resolve_captcha_code
validate_input = flow_module.validate_input


REQUESTED_LINES = [
    {
        "lineNo": "10",
        "materialNo": "1B.30040.020262",
        "expectedDeliveryDate": "2026-08-10",
    },
    {
        "lineNo": "20",
        "materialNo": "1B.30040.020262",
        "expectedDeliveryDate": "2026-08-12",
    },
]
RAW_LINES = [
    {
        "lineNo": "10",
        "materialNo": "1B.30040.020262",
        "currentExpectedDate": "",
    },
    {
        "lineNo": "20",
        "materialNo": "1B.30040.020262",
        "currentExpectedDate": "2026-08-01",
    },
]
PERSISTED_LINES = [
    {
        **line,
        "currentExpectedDate": line["expectedDeliveryDate"],
    }
    for line in REQUESTED_LINES
]


def task_input(lines=None):
    resolved = REQUESTED_LINES if lines is None else lines
    return {
        "po_no": "POJS2607130002",
        "order_lines": [
            {
                "line_number": line["lineNo"],
                "material_number": line["materialNo"],
                "expected_delivery_date": line["expectedDeliveryDate"],
            }
            for line in resolved
        ],
    }


class RecordingEvents:
    def __init__(self):
        self.items = []

    async def emit(self, event_type, **kwargs):
        self.items.append({"type": event_type, **kwargs})


class RecordingArtifacts:
    def __init__(self, timeline=None):
        self.items = []
        self.timeline = timeline

    async def screenshot(self, name, *, step_id):
        self.items.append((name, step_id))
        if self.timeline is not None:
            self.timeline.append(("screenshot", name))


class RecordingLog:
    async def info(self, *_args, **_kwargs):
        return None


def make_ctx(input_value=None):
    return SimpleNamespace(
        input=task_input() if input_value is None else input_value,
        portal_url="http://portal.test/",
        credentials={"username": "tester", "password": "not-logged"},
        selectors={},
        events=RecordingEvents(),
        artifacts=RecordingArtifacts(),
        log=RecordingLog(),
        page=SimpleNamespace(),
    )


class InputValidationTests(unittest.TestCase):
    def test_accepts_duplicate_materials_on_distinct_order_lines(self):
        po_no, lines = validate_input(task_input())

        self.assertEqual(po_no, "POJS2607130002")
        self.assertEqual(lines, REQUESTED_LINES)
        self.assertEqual(lines[0]["materialNo"], lines[1]["materialNo"])
        self.assertNotEqual(
            lines[0]["expectedDeliveryDate"],
            lines[1]["expectedDeliveryDate"],
        )

    def test_accepts_engine_read_only_input_mapping(self):
        value = task_input()
        value["order_lines"] = [MappingProxyType(line) for line in value["order_lines"]]

        po_no, lines = validate_input(MappingProxyType(value))

        self.assertEqual(po_no, "POJS2607130002")
        self.assertEqual(lines, REQUESTED_LINES)

    def test_rejects_invalid_order_number(self):
        for po_no in ("", "../POJS2607130002", "PO WITH SPACES"):
            with self.subTest(po_no=po_no):
                value = task_input()
                value["po_no"] = po_no
                with self.assertRaises(RpaBusinessError) as captured:
                    validate_input(value)
                self.assertEqual(captured.exception.code, "FLOW_INPUT_INVALID")

    def test_requires_non_empty_order_lines_array(self):
        cases = (None, {}, "not-an-array", [])
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(RpaBusinessError) as captured:
                    validate_input(
                        {
                            "po_no": "POJS2607130002",
                            "order_lines": value,
                        }
                    )
                self.assertEqual(
                    captured.exception.code,
                    "DELIVERY_DATE_MAPPING_INVALID",
                )

    def test_rejects_duplicate_line_number(self):
        duplicate = [REQUESTED_LINES[0], {**REQUESTED_LINES[1], "lineNo": "10"}]

        with self.assertRaises(RpaBusinessError) as captured:
            validate_input(task_input(duplicate))

        self.assertEqual(
            captured.exception.code,
            "DELIVERY_DATE_MAPPING_INVALID",
        )

    def test_rejects_missing_material_number(self):
        value = task_input()
        value["order_lines"][0]["material_number"] = ""

        with self.assertRaises(RpaBusinessError) as captured:
            validate_input(value)

        self.assertEqual(
            captured.exception.code,
            "DELIVERY_DATE_MAPPING_INVALID",
        )

    def test_rejects_bad_date_format_and_impossible_date(self):
        for bad_date in ("2026/08/10", "2026-02-30"):
            with self.subTest(bad_date=bad_date):
                value = task_input()
                value["order_lines"][0]["expected_delivery_date"] = bad_date
                with self.assertRaises(RpaBusinessError) as captured:
                    validate_input(value)
                self.assertEqual(
                    captured.exception.code,
                    "DELIVERY_DATE_MAPPING_INVALID",
                )

    def test_captcha_mapping_keeps_unknown_as_human_boundary(self):
        self.assertEqual(resolve_captcha_code("/captcha/code03.png"), "sez0")
        self.assertIsNone(resolve_captcha_code("/captcha/new-code.png"))


class DetailNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_clicks_search_result_detail_and_accepts_both_page_types(self):
        class Locator:
            def __init__(self, page, selector):
                self.page = page
                self.selector = selector

            async def wait_for(self, *, state, timeout):  # noqa: ASYNC109
                self.page.waits.append((self.selector, state, timeout))

        class Page:
            def __init__(self):
                self.gotos = []
                self.fills = []
                self.clicks = []
                self.waits = []

            async def goto(self, url, *, wait_until):
                self.gotos.append((url, wait_until))

            async def fill(self, selector, value):
                self.fills.append((selector, value))

            async def click(self, selector):
                self.clicks.append(selector)

            def locator(self, selector):
                return Locator(self, selector)

        selectors = {
            "order_page": "[orders]",
            "po_number": "[po-number]",
            "search_button": "[search]",
            "order_row": "[row-{po_no}]",
            "order_detail": "[detail-{po_no}]",
            "detail_page": "[normal-page], [pending-page]",
            "detail_po_number": "[normal-no-{po_no}], [pending-no-{po_no}]",
            "lines_table": "[normal-lines], [pending-lines]",
        }
        page = Page()
        ctx = SimpleNamespace(
            page=page,
            selectors=selectors,
            portal_url="http://portal.test/",
            events=RecordingEvents(),
        )
        adapter = flow_module.SupplierPortalDeliveryDateAdapter(ctx)

        await adapter.open_order_detail("POJS2607130002")

        self.assertEqual(
            page.gotos,
            [("http://portal.test/#/supplier/orders", "domcontentloaded")],
        )
        self.assertEqual(page.clicks, ["[search]", "[detail-POJS2607130002]"])
        self.assertNotIn("/#/supplier/pend-orders/", str(page.gotos))
        waited_selectors = [item[0] for item in page.waits]
        self.assertIn("[normal-page], [pending-page]", waited_selectors)
        self.assertIn(
            "[normal-no-POJS2607130002], [pending-no-POJS2607130002]",
            waited_selectors,
        )
        self.assertIn("[normal-lines], [pending-lines]", waited_selectors)


class ReconciliationTests(unittest.TestCase):
    def test_matches_by_line_and_allows_duplicate_material_numbers(self):
        result = reconcile_order_lines(RAW_LINES, REQUESTED_LINES)

        self.assertEqual([line["lineNo"] for line in result], ["10", "20"])
        self.assertEqual(result[0]["materialNo"], result[1]["materialNo"])
        self.assertEqual(result[0]["expectedDeliveryDate"], "2026-08-10")
        self.assertEqual(result[1]["expectedDeliveryDate"], "2026-08-12")

    def test_latest_portal_date_wins_during_post_save_reconciliation(self):
        initially_resolved = reconcile_order_lines(RAW_LINES, REQUESTED_LINES)

        persisted = reconcile_order_lines(PERSISTED_LINES, initially_resolved)

        self.assertTrue(flow_module._dates_match(persisted))
        self.assertEqual(persisted[1]["currentExpectedDate"], "2026-08-12")

    def test_rejects_missing_and_extra_lines(self):
        cases = (
            (REQUESTED_LINES[:1], ["20"], []),
            (
                [
                    *REQUESTED_LINES,
                    {
                        "lineNo": "30",
                        "materialNo": "ITEM-30",
                        "expectedDeliveryDate": "2026-08-30",
                    },
                ],
                [],
                ["30"],
            ),
        )
        for requested, missing, extra in cases:
            with self.subTest(requested=requested):
                with self.assertRaises(RpaBusinessError) as captured:
                    reconcile_order_lines(RAW_LINES, requested)
                self.assertEqual(
                    captured.exception.code,
                    "DELIVERY_DATE_LINE_MISMATCH",
                )
                self.assertEqual(
                    captured.exception.details["missingLineNumbers"],
                    missing,
                )
                self.assertEqual(
                    captured.exception.details["extraLineNumbers"],
                    extra,
                )

    def test_rejects_material_mismatch_for_matching_line_number(self):
        requested = [dict(line) for line in REQUESTED_LINES]
        requested[1]["materialNo"] = "WRONG-MATERIAL"

        with self.assertRaises(RpaBusinessError) as captured:
            reconcile_order_lines(RAW_LINES, requested)

        self.assertEqual(
            captured.exception.code,
            "DELIVERY_DATE_LINE_MISMATCH",
        )
        self.assertEqual(
            captured.exception.details["materialMismatches"][0]["lineNo"],
            "20",
        )

    def test_rejects_duplicate_portal_line_number_as_ambiguous(self):
        duplicate = [RAW_LINES[0], {**RAW_LINES[1], "lineNo": "10"}]

        with self.assertRaises(RpaBusinessError) as captured:
            reconcile_order_lines(duplicate, REQUESTED_LINES)

        self.assertEqual(
            captured.exception.code,
            "ORDER_LINE_DATA_AMBIGUOUS",
        )

    def test_rejects_missing_portal_lines(self):
        with self.assertRaises(RpaBusinessError) as captured:
            reconcile_order_lines([], REQUESTED_LINES)

        self.assertEqual(captured.exception.code, "ORDER_LINES_NOT_FOUND")


class RunOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_multi_line_save_and_sign_success(self):
        calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                calls.append("login")

            async def open_order_detail(self, po_no):
                calls.append(("open", po_no))

            async def collect_order_lines(self):
                calls.append("collect")
                return RAW_LINES

            async def reply_status(self):
                return "待签章"

            async def ensure_editable(self, lines):
                calls.append(("editable", len(lines)))

            async def fill_and_verify(self, lines):
                calls.append(
                    (
                        "fill",
                        [
                            (
                                line["lineNo"],
                                line["materialNo"],
                                line["expectedDeliveryDate"],
                            )
                            for line in lines
                        ],
                    )
                )

            async def capture_stable_screenshot(
                self,
                name,
                _step_id,
                _lines,
                *,
                expected_status=None,
            ):
                calls.append(("stable-screenshot", name, expected_status))

            async def capture_failure_screenshot(self, name, _step_id):
                calls.append(("failure-screenshot", name))

            async def save_and_verify(self, po_no, lines):
                calls.append(("save", po_no, len(lines)))
                persisted = reconcile_order_lines(PERSISTED_LINES, lines)
                return "已按明细行保存预计交货日期（2 行）", persisted

            async def sign_and_verify(self, po_no, lines):
                calls.append(("sign", po_no, len(lines)))
                return (
                    "签章成功，回复状态已更新为已回签",
                    "已回签",
                    lines,
                )

        original = flow_module.SupplierPortalDeliveryDateAdapter
        flow_module.SupplierPortalDeliveryDateAdapter = FakeAdapter
        try:
            result = await flow_module.run(make_ctx())
        finally:
            flow_module.SupplierPortalDeliveryDateAdapter = original

        self.assertEqual(
            [call for call in calls if isinstance(call, tuple) and call[0] == "save"],
            [("save", "POJS2607130002", 2)],
        )
        self.assertEqual(
            [call for call in calls if isinstance(call, tuple) and call[0] == "sign"],
            [("sign", "POJS2607130002", 2)],
        )
        screenshots = [
            call[1]
            for call in calls
            if isinstance(call, tuple) and call[0] == "stable-screenshot"
        ]
        self.assertEqual(
            screenshots,
            [
                "supplier-portal-delivery-dates-before-save",
                "supplier-portal-delivery-dates-saved",
                "supplier-portal-delivery-dates-signed",
            ],
        )
        self.assertTrue(result["saved"])
        self.assertTrue(result["signed"])
        self.assertEqual(result["replyStatus"], "已回签")
        self.assertEqual(result["lineCount"], 2)
        self.assertEqual(
            result["lines"][0]["expectedDeliveryDate"],
            "2026-08-10",
        )
        self.assertEqual(
            result["lines"][1]["expectedDeliveryDate"],
            "2026-08-12",
        )

    async def test_line_mismatch_stops_before_page_mutation(self):
        calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                calls.append("login")

            async def open_order_detail(self, _po_no):
                calls.append("open")

            async def collect_order_lines(self):
                calls.append("collect")
                return RAW_LINES

            async def reply_status(self):
                calls.append("status")
                return "待签章"

            async def ensure_editable(self, _lines):
                calls.append("editable")

            async def fill_and_verify(self, _lines):
                calls.append("fill")

            async def save_and_verify(self, *_args):
                calls.append("save")

            async def sign_and_verify(self, *_args):
                calls.append("sign")

        original = flow_module.SupplierPortalDeliveryDateAdapter
        flow_module.SupplierPortalDeliveryDateAdapter = FakeAdapter
        try:
            with self.assertRaises(RpaBusinessError) as captured:
                await flow_module.run(make_ctx(task_input(REQUESTED_LINES[:1])))
        finally:
            flow_module.SupplierPortalDeliveryDateAdapter = original

        self.assertEqual(
            captured.exception.code,
            "DELIVERY_DATE_LINE_MISMATCH",
        )
        self.assertEqual(calls, ["login", "open", "collect"])

    async def test_already_signed_matching_dates_is_idempotent_success(self):
        calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                calls.append("login")

            async def open_order_detail(self, _po_no):
                calls.append("open")

            async def collect_order_lines(self):
                return PERSISTED_LINES

            async def reply_status(self):
                return "已回签"

            async def ensure_sign_not_executable(self):
                calls.append("sign-disabled")

            async def capture_stable_screenshot(
                self,
                name,
                _step_id,
                _lines,
                *,
                expected_status=None,
            ):
                calls.append(("screenshot", name, expected_status))

            async def fill_and_verify(self, _lines):
                calls.append("fill")

            async def save_and_verify(self, *_args):
                calls.append("save")

            async def sign_and_verify(self, *_args):
                calls.append("sign")

        original = flow_module.SupplierPortalDeliveryDateAdapter
        flow_module.SupplierPortalDeliveryDateAdapter = FakeAdapter
        try:
            result = await flow_module.run(make_ctx())
        finally:
            flow_module.SupplierPortalDeliveryDateAdapter = original

        self.assertTrue(result["signed"])
        self.assertEqual(result["replyStatus"], "已回签")
        self.assertNotIn("fill", calls)
        self.assertNotIn("save", calls)
        self.assertNotIn("sign", calls)
        self.assertIn("sign-disabled", calls)

    async def test_unreadable_reply_status_stops_before_any_write(self):
        calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                calls.append("login")

            async def open_order_detail(self, _po_no):
                calls.append("open")

            async def collect_order_lines(self):
                calls.append("collect")
                return PERSISTED_LINES

            async def reply_status(self):
                calls.append("status")
                raise RpaRetryableError(
                    "ORDER_REPLY_STATUS_UNAVAILABLE",
                    "无法读取订单回复状态。",
                )

            async def fill_and_verify(self, _lines):
                calls.append("fill")

            async def save_and_verify(self, *_args):
                calls.append("save")

            async def sign_and_verify(self, *_args):
                calls.append("sign")

        original = flow_module.SupplierPortalDeliveryDateAdapter
        flow_module.SupplierPortalDeliveryDateAdapter = FakeAdapter
        try:
            with self.assertRaises(RpaRetryableError) as captured:
                await flow_module.run(make_ctx())
        finally:
            flow_module.SupplierPortalDeliveryDateAdapter = original

        self.assertEqual(
            captured.exception.code,
            "ORDER_REPLY_STATUS_UNAVAILABLE",
        )
        self.assertEqual(calls, ["login", "open", "collect", "status"])


class FakeLoadingLocator:
    def __init__(self, timeline):
        self.timeline = timeline

    async def wait_for(self, *, state, timeout):  # noqa: ASYNC109
        self.timeline.append(("loading", state, timeout))


class FakeStablePage:
    def __init__(self, loading_selector, timeline):
        self.loading_selector = loading_selector
        self.timeline = timeline
        self.layout = {
            "x": 0,
            "y": 0,
            "width": 1200,
            "height": 900,
            "scrollWidth": 1200,
            "scrollHeight": 900,
            "bodyHeight": 900,
        }

    def locator(self, selector):
        if selector == self.loading_selector:
            return FakeLoadingLocator(self.timeline)
        raise AssertionError(f"Unexpected selector: {selector}")

    async def evaluate(self, script, *_args):
        if "document.fonts" in script:
            self.timeline.append(("evaluate", "fonts-and-images"))
            return None
        if "getBoundingClientRect" in script:
            self.timeline.append(("evaluate", "layout"))
            return dict(self.layout)
        raise AssertionError("Unexpected evaluate script")

    async def wait_for_timeout(self, milliseconds):
        self.timeline.append(("timeout", milliseconds))


class StabilityAndReadOnlyTests(unittest.IsolatedAsyncioTestCase):
    async def test_screenshot_occurs_only_after_full_stability_gate(self):
        timeline = []
        selectors = {"loading_mask": "[loading]"}
        page = FakeStablePage(selectors["loading_mask"], timeline)
        ctx = SimpleNamespace(
            page=page,
            selectors=selectors,
            artifacts=RecordingArtifacts(timeline),
        )
        adapter = flow_module.SupplierPortalDeliveryDateAdapter(ctx)

        async def collect():
            timeline.append(("collect", len(PERSISTED_LINES)))
            return PERSISTED_LINES

        async def status():
            timeline.append(("status", "已回签"))
            return "已回签"

        adapter.collect_order_lines = collect
        adapter.reply_status = status

        await adapter.capture_stable_screenshot(
            "supplier-portal-delivery-dates-signed",
            "srm.sign_order",
            REQUESTED_LINES,
            expected_status="已回签",
        )

        self.assertEqual(timeline[0], ("loading", "hidden", 15000))
        self.assertIn(("evaluate", "fonts-and-images"), timeline)
        self.assertGreaterEqual(timeline.count(("evaluate", "layout")), 2)
        self.assertEqual(timeline[-2], ("timeout", 300))
        self.assertEqual(
            timeline[-1],
            ("screenshot", "supplier-portal-delivery-dates-signed"),
        )

    async def test_read_only_signed_rows_do_not_require_date_inputs(self):
        class ReadOnlyPage:
            def __init__(self):
                self.script = ""

            async def evaluate(self, script, table_selector):
                self.script = script
                self.table_selector = table_selector
                return PERSISTED_LINES

        page = ReadOnlyPage()
        adapter = flow_module.SupplierPortalDeliveryDateAdapter(
            SimpleNamespace(
                page=page,
                selectors={"lines_table": "[lines-table]"},
            )
        )

        lines = await adapter.collect_order_lines()

        self.assertEqual(lines, PERSISTED_LINES)
        self.assertEqual(page.table_selector, "[lines-table]")
        self.assertIn("headers.indexOf('预计交货日期')", page.script)
        self.assertIn("cells[expectedDateIndex]", page.script)
        self.assertNotIn("cells[12]", page.script)
        self.assertNotIn(".locator(", page.script)

    async def test_signed_normal_detail_allows_absent_sign_button(self):
        class MissingSignLocator:
            async def is_visible(self):
                return False

            async def is_enabled(self):
                raise AssertionError("An absent sign button must not be enabled")

        class ReadOnlySignedPage:
            def locator(self, selector):
                self.selector = selector
                return MissingSignLocator()

        page = ReadOnlySignedPage()
        adapter = flow_module.SupplierPortalDeliveryDateAdapter(
            SimpleNamespace(
                page=page,
                selectors={"sign": "[pending-sign]:visible"},
            )
        )

        await adapter.ensure_sign_not_executable()

        self.assertEqual(page.selector, "[pending-sign]:visible")


class PackageContractTests(unittest.TestCase):
    def test_manifest_and_selectors_use_line_array_and_sign_action(self):
        manifest = json.loads((FLOW_DIR / "manifest.json").read_text(encoding="utf-8"))
        selectors = json.loads(
            (FLOW_DIR / "selectors.json").read_text(encoding="utf-8")
        )

        input_fields = {item["name"]: item for item in manifest["inputSchema"]}
        self.assertNotIn("delivery_dates", input_fields)
        self.assertEqual(input_fields["order_lines"]["type"], "array")
        self.assertTrue(input_fields["order_lines"]["required"])
        self.assertEqual(manifest["version"], "1.0.1")
        self.assertIn("pend-order-detail-sign-btn", selectors["sign"])
        self.assertTrue(selectors["sign"].endswith(":visible"))
        self.assertIn("order-detail-page", selectors["detail_page"])
        self.assertIn("pend-order-detail-page", selectors["detail_page"])
        self.assertIn("order-detail-no-{po_no}", selectors["detail_po_number"])
        self.assertIn(
            "pend-order-detail-no-{po_no}",
            selectors["detail_po_number"],
        )
        self.assertIn("order-detail-lines-table", selectors["lines_table"])
        self.assertIn("pend-order-detail-lines-table", selectors["lines_table"])
        self.assertIn("order-detail-page", selectors["reply_status"])
        self.assertIn("pend-order-detail-page", selectors["reply_status"])
        self.assertNotIn("save_line", selectors)

    def test_flow_does_not_reference_per_line_save_control(self):
        source = (FLOW_DIR / "flow.py").read_text(encoding="utf-8")

        self.assertNotIn("pend-order-detail-save-line", source)
        self.assertNotIn("save_line", source)
        self.assertNotIn("/#/supplier/pend-orders/{po_no}", source)
        self.assertIn("[data-rpa=order-detail-page]", source)
        self.assertIn("[data-rpa=pend-order-detail-page]", source)


class FakeLocator:
    def __init__(self, *, text="", enabled=True, click_error=None):
        self.text = text
        self.enabled = enabled
        self.click_error = click_error
        self.click_count = 0
        self.wait_count = 0

    async def click(self, **_kwargs):
        self.click_count += 1
        if self.click_error is not None:
            raise self.click_error

    async def wait_for(self, **_kwargs):
        self.wait_count += 1

    async def is_visible(self):
        return True

    async def is_enabled(self):
        return self.enabled

    async def inner_text(self):
        return self.text


class FakeActionPage:
    def __init__(self, selectors, *, save_error=None, sign_error=None):
        self.selectors = selectors
        self.save = FakeLocator(click_error=save_error)
        self.sign = FakeLocator(click_error=sign_error)
        self.detail = FakeLocator()
        self.status = FakeLocator(text="已回签")
        self.reload_count = 0

    def locator(self, selector):
        if selector == self.selectors["save_all"]:
            return self.save
        if selector == self.selectors["sign"]:
            return self.sign
        if selector.startswith("[detail-"):
            return self.detail
        if selector == self.selectors["reply_status"]:
            return self.status
        raise AssertionError(f"Unexpected selector: {selector}")

    async def reload(self, **_kwargs):
        self.reload_count += 1
        self.sign.enabled = False


class ActionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def make_adapter(self, *, save_error=None, sign_error=None):
        selectors = {
            "save_all": "[save]",
            "sign": "[sign]",
            "detail_po_number": "[detail-{po_no}]",
            "reply_status": "[reply-status]",
        }
        page = FakeActionPage(
            selectors,
            save_error=save_error,
            sign_error=sign_error,
        )
        ctx = SimpleNamespace(page=page, selectors=selectors)
        adapter = flow_module.SupplierPortalDeliveryDateAdapter(ctx)
        return adapter, page

    async def test_save_clicks_top_button_once_and_reloads_persisted_lines(self):
        adapter, page = self.make_adapter()

        async def result(**_kwargs):
            return "已按明细行保存预计交货日期（2 行）"

        async def collect():
            return PERSISTED_LINES

        adapter._wait_for_action_result = result
        adapter.collect_order_lines = collect

        message, lines = await adapter.save_and_verify(
            "POJS2607130002",
            REQUESTED_LINES,
        )

        self.assertIn("已按明细行保存预计交货日期", message)
        self.assertEqual(page.save.click_count, 1)
        self.assertEqual(page.reload_count, 1)
        self.assertTrue(flow_module._dates_match(lines))

    async def test_save_rejection_is_business_failure(self):
        adapter, page = self.make_adapter()

        async def rejected(**_kwargs):
            raise RpaBusinessError(
                "ORDER_DATE_SAVE_REJECTED",
                "save rejected",
            )

        adapter._wait_for_action_result = rejected

        with self.assertRaises(RpaBusinessError) as captured:
            await adapter.save_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(captured.exception.code, "ORDER_DATE_SAVE_REJECTED")
        self.assertEqual(page.save.click_count, 1)

    async def test_save_unknown_result_requires_human_without_second_click(self):
        adapter, page = self.make_adapter()

        async def unknown(**_kwargs):
            raise RpaHumanRequiredError(
                "ORDER_DATE_SAVE_OUTCOME_UNKNOWN",
                "unknown",
            )

        adapter._wait_for_action_result = unknown

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.save_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_DATE_SAVE_OUTCOME_UNKNOWN",
        )
        self.assertEqual(page.save.click_count, 1)

    async def test_save_click_cancellation_requires_human(self):
        adapter, page = self.make_adapter(save_error=asyncio.CancelledError())

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.save_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_DATE_SAVE_OUTCOME_UNKNOWN",
        )
        self.assertEqual(page.save.click_count, 1)

    async def test_sign_clicks_once_reloads_and_confirms_disabled_action(self):
        adapter, page = self.make_adapter()

        async def result(**_kwargs):
            return "签章成功，回复状态已更新为已回签"

        async def collect():
            return PERSISTED_LINES

        adapter._wait_for_action_result = result
        adapter.collect_order_lines = collect

        message, status, lines = await adapter.sign_and_verify(
            "POJS2607130002",
            REQUESTED_LINES,
        )

        self.assertIn("签章成功", message)
        self.assertEqual(status, "已回签")
        self.assertEqual(page.sign.click_count, 1)
        self.assertEqual(page.reload_count, 1)
        self.assertFalse(page.sign.enabled)
        self.assertTrue(flow_module._dates_match(lines))

    async def test_sign_rejection_is_business_failure(self):
        adapter, page = self.make_adapter()

        async def rejected(**_kwargs):
            raise RpaBusinessError("ORDER_SIGN_REJECTED", "sign rejected")

        adapter._wait_for_action_result = rejected

        with self.assertRaises(RpaBusinessError) as captured:
            await adapter.sign_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(captured.exception.code, "ORDER_SIGN_REJECTED")
        self.assertEqual(page.sign.click_count, 1)

    async def test_sign_unknown_result_requires_human_without_second_click(self):
        adapter, page = self.make_adapter()

        async def unknown(**_kwargs):
            raise RpaHumanRequiredError(
                "ORDER_SIGN_OUTCOME_UNKNOWN",
                "unknown",
            )

        adapter._wait_for_action_result = unknown

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.sign_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_SIGN_OUTCOME_UNKNOWN",
        )
        self.assertEqual(page.sign.click_count, 1)

    async def test_sign_click_cancellation_requires_human(self):
        adapter, page = self.make_adapter(sign_error=asyncio.CancelledError())

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.sign_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_SIGN_OUTCOME_UNKNOWN",
        )
        self.assertEqual(page.sign.click_count, 1)

    async def test_save_persistence_mismatch_requires_human(self):
        adapter, page = self.make_adapter()

        async def result(**_kwargs):
            return "已按明细行保存预计交货日期（2 行）"

        async def collect():
            return [
                PERSISTED_LINES[0],
                {**PERSISTED_LINES[1], "currentExpectedDate": "2026-08-11"},
            ]

        adapter._wait_for_action_result = result
        adapter.collect_order_lines = collect

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.save_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_DATE_PERSISTENCE_UNCONFIRMED",
        )
        self.assertEqual(page.save.click_count, 1)

    async def test_sign_success_with_wrong_status_requires_human(self):
        adapter, page = self.make_adapter()
        page.status.text = "待签章"

        async def result(**_kwargs):
            return "签章成功，回复状态已更新为已回签"

        adapter._wait_for_action_result = result

        with self.assertRaises(RpaHumanRequiredError) as captured:
            await adapter.sign_and_verify(
                "POJS2607130002",
                REQUESTED_LINES,
            )

        self.assertEqual(
            captured.exception.code,
            "ORDER_SIGN_STATUS_UNCONFIRMED",
        )
        self.assertEqual(page.sign.click_count, 1)

    async def test_already_signed_conflicting_date_requires_human(self):
        calls = []

        class FakeAdapter:
            def __init__(self, _ctx):
                pass

            async def login(self):
                return None

            async def open_order_detail(self, _po_no):
                return None

            async def collect_order_lines(self):
                return [
                    PERSISTED_LINES[0],
                    {**PERSISTED_LINES[1], "currentExpectedDate": "2026-08-11"},
                ]

            async def reply_status(self):
                return "已回签"

            async def capture_failure_screenshot(self, name, _step_id):
                calls.append(("failure-screenshot", name))

            async def fill_and_verify(self, _lines):
                calls.append("fill")

            async def save_and_verify(self, *_args):
                calls.append("save")

            async def sign_and_verify(self, *_args):
                calls.append("sign")

        original = flow_module.SupplierPortalDeliveryDateAdapter
        flow_module.SupplierPortalDeliveryDateAdapter = FakeAdapter
        try:
            with self.assertRaises(RpaHumanRequiredError) as captured:
                await flow_module.run(make_ctx())
        finally:
            flow_module.SupplierPortalDeliveryDateAdapter = original

        self.assertEqual(
            captured.exception.code,
            "ORDER_ALREADY_CONFIRMED_CONFLICT",
        )
        self.assertNotIn("fill", calls)
        self.assertNotIn("save", calls)
        self.assertNotIn("sign", calls)


if __name__ == "__main__":
    unittest.main()
