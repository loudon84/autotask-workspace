"""statement_bills 模型单测（不连库）。"""

from datetime import date
from decimal import Decimal

from app.models.statement_bill import StatementBill


def test_statement_bill_defaults():
    bill = StatementBill(
        tenant_id="t1",
        process_instance_id="p1",
        portal_account_id="pa1",
        check_date=date(2026, 8, 17),
        check_amount=Decimal("100.00"),
        created_by="u1",
        check_status="UNCHECKED",
        invoice_status="NOT_UPLOADED",
    )
    assert bill.check_status == "UNCHECKED"
    assert bill.invoice_status == "NOT_UPLOADED"
    assert bill.invoice_no is None
    assert bill.invoice_amount is None
    assert bill.last_error is None


def test_statement_bill_column_defaults():
    # 列级 default 在 INSERT 时生效（对齐现有模型写法）
    assert StatementBill.__table__.c.check_status.default.arg == "UNCHECKED"
    assert StatementBill.__table__.c.invoice_status.default.arg == "NOT_UPLOADED"


def test_statement_bill_table_name_and_constraint():
    assert StatementBill.__tablename__ == "statement_bills"
    constraint_names = {
        arg.name for arg in StatementBill.__table_args__ if getattr(arg, "name", None)
    }
    assert "uq_statement_bills_tenant_date_amount" in constraint_names
    assert "ix_statement_bills_tenant_check_status" in constraint_names
