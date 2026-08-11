import io
import unittest
import zipfile
from xml.sax.saxutils import escape

from nodeskclaw_rpa_engine.runtime import RpaBusinessError

from flow import build_erp_draft, parse_order_xlsx


HEADERS = [
    "供应商编号",
    "供应商名称",
    "订单编号",
    "订单行号",
    "料号",
    "料品名称",
    "料品规格",
    "物料状态",
    "内码",
    "数量",
    "单位",
    "单价（元）",
    "价税合计（元）",
    "要求交货日期",
    "标准交货日期（天）",
    "是否满足LT",
    "供方交期",
    "欠交数量",
    "备注",
    "直发备注",
]
ROW = [
    "02556",
    "深圳市芯云信息科技有限公司",
    "POJS2606030010",
    "10",
    "1B.30040.020227",
    "芯片-视频编解码",
    "[SSC335]-(B)-QFN88(9x9mm)-sigmastar",
    "A",
    "221316",
    "31200.0",
    "个",
    "22.9448",
    "715877.76",
    "2026-06-24",
    "42",
    "否",
    "2026-08-31",
    "20800.0",
    "",
    "是否中性:否;",
]


def column_name(index):
    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def make_xlsx(headers=HEADERS, rows=None):
    rows = rows or [ROW]
    values = []
    indexes = {}
    for value in [*headers, *(item for row in rows for item in row)]:
        text = str(value)
        if text not in indexes:
            indexes[text] = len(values)
            values.append(text)
    shared = "".join(f"<si><t>{escape(value)}</t></si>" for value in values)

    def xml_row(number, row):
        cells = "".join(
            f'<c r="{column_name(index)}{number}" t="s"><v>{indexes[str(value)]}</v></c>'
            for index, value in enumerate(row)
        )
        return f'<row r="{number}">{cells}</row>'

    sheet_rows = xml_row(1, headers) + "".join(
        xml_row(index + 2, row) for index, row in enumerate(rows)
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"{shared}</sst>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{sheet_rows}</sheetData></worksheet>",
        )
    return output.getvalue()


class OrderXlsxTests(unittest.TestCase):
    def test_extracts_every_attachment_business_field(self):
        result = parse_order_xlsx(make_xlsx())

        self.assertEqual(result["supplierCode"], "02556")
        self.assertEqual(result["supplierName"], "深圳市芯云信息科技有限公司")
        self.assertEqual(len(result["lines"]), 1)
        line = result["lines"][0]
        self.assertEqual(line["poNo"], "POJS2606030010")
        self.assertEqual(line["lineNumber"], "10")
        self.assertEqual(line["customerItemNumber"], "1B.30040.020227")
        self.assertEqual(line["orderQuantity"], "31200.0")
        self.assertEqual(line["unitSellingPrice"], "22.9448")
        self.assertEqual(line["requestDate"], "2026-06-24")
        self.assertEqual(line["directShipmentRemarks"], "是否中性:否;")

    def test_rejects_missing_required_attachment_column(self):
        headers = [item for item in HEADERS if item != "订单行号"]
        row = [value for index, value in enumerate(ROW) if HEADERS[index] != "订单行号"]

        with self.assertRaises(RpaBusinessError) as captured:
            parse_order_xlsx(make_xlsx(headers, [row]))

        self.assertEqual(captured.exception.code, "ORDER_ATTACHMENT_DATA_INCOMPLETE")

    def test_rejects_inconsistent_attachment_supplier(self):
        second = list(ROW)
        second[1] = "另一供应商"
        second[3] = "20"

        with self.assertRaises(RpaBusinessError) as captured:
            parse_order_xlsx(make_xlsx(rows=[ROW, second]))

        self.assertEqual(captured.exception.code, "ORDER_ATTACHMENT_DATA_INVALID")


class ErpDraftTests(unittest.TestCase):
    def test_uses_only_xlsx_mapping_and_declared_defaults(self):
        attachment = parse_order_xlsx(make_xlsx())

        payload, resolved = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        header = payload[0]
        line = header["lines"][0]
        self.assertEqual(header["orderNumber"], "")
        self.assertEqual(header["customerNumber"], "")
        self.assertEqual(header["customerName"], "天地偉業技術有限公司")
        self.assertEqual(header["orderType"], "常规订单")
        self.assertEqual(header["orderedDate"], "2026-07-22")
        self.assertEqual(header["currencyCode"], "")
        self.assertEqual(header["orgName"], "深圳市芯云信息科技有限公司")
        self.assertEqual(header["paymentTerm"], "")
        self.assertEqual(header["comments"], "")
        self.assertEqual(header["isAttachment"], "Y")
        for name in (
            "salesrep",
            "invoiceToLocation",
            "orgCode",
            "priceListName",
            "fobPointCode",
            "fob",
            "userNo",
            "sourceHeaderId",
        ):
            self.assertEqual(header[name], "", name)
        self.assertEqual(line["lineNumber"], "")
        self.assertEqual(line["lineType"], "")
        self.assertEqual(line["custPoLine"], "10")
        self.assertEqual(line["custPoNumber"], "POJS2606030010")
        self.assertEqual(line["custItemNum"], "1B.30040.020227")
        self.assertEqual(line["itemNumber"], "")
        self.assertEqual(line["itemDescription"], "")
        self.assertEqual(line["orderQuantity"], 31200)
        self.assertEqual(line["orderQuantityUom"], "")
        self.assertEqual(line["unitSellingPrice"], 22.9448)
        self.assertEqual(line["taxRate"], 0.13)
        self.assertEqual(line["unTaxPrice"], "20.3051")
        self.assertEqual(line["requestDate"], "2026-06-24")
        for name in (
            "priceListName",
            "factoryLocation",
            "customerJob",
            "productLine",
            "pm",
            "usdPrice",
            "deliveryRate",
            "actualExchangeRate",
            "sourceLineId",
        ):
            self.assertEqual(line[name], "", name)
        self.assertEqual(resolved[0]["taxRate"], "0.13")

    def test_does_not_map_direct_shipment_remarks_to_comments(self):
        attachment = parse_order_xlsx(make_xlsx())

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        self.assertEqual(attachment["lines"][0]["directShipmentRemarks"], "是否中性:否;")
        self.assertEqual(payload[0]["comments"], "")

    def test_maps_distinct_xlsx_remarks_to_header_comments(self):
        first = list(ROW)
        first[18] = "请整单交付"
        second = list(ROW)
        second[3] = "20"
        second[18] = "防潮包装"
        attachment = parse_order_xlsx(make_xlsx(rows=[first, second]))

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        self.assertEqual(payload[0]["comments"], "请整单交付；防潮包装")

    def test_rejects_attachment_for_another_purchase_order(self):
        row = list(ROW)
        row[2] = "PO-OTHER"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))

        with self.assertRaises(RpaBusinessError) as captured:
            build_erp_draft(
                "POJS2606030010",
                attachment,
                ordered_date="2026-07-22",
            )

        self.assertEqual(captured.exception.code, "ORDER_ATTACHMENT_PO_MISMATCH")

    def test_preserves_xlsx_purchase_order_value_in_payload(self):
        row = list(ROW)
        row[2] = "pojs2606030010"
        attachment = parse_order_xlsx(make_xlsx(rows=[row]))

        payload, _ = build_erp_draft(
            "POJS2606030010",
            attachment,
            ordered_date="2026-07-22",
        )

        self.assertEqual(
            payload[0]["lines"][0]["custPoNumber"],
            "pojs2606030010",
        )


if __name__ == "__main__":
    unittest.main()
