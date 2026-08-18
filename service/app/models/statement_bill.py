"""天地伟业对账单头表。

只跟踪本系统创建的对账单；不存收货明细（明细由 RPA 实时从 SRM 读取）。
匹配键：check_date + check_amount（SRM 无可用对账单号）。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class StatementBill(BaseModel):
    __tablename__ = "statement_bills"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "check_date",
            "check_amount",
            name="uq_statement_bills_tenant_date_amount",
        ),
        Index("ix_statement_bills_tenant_check_status", "tenant_id", "check_status"),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    process_instance_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    portal_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # UNCHECKED(未对账) / CHECKED(已对账) / VOID(已作废) / DRAFT(待生成，本系统草稿)
    check_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNCHECKED")
    # NOT_UPLOADED(未上传) / UPLOADED(已上传) / REVIEWING(审批中)
    invoice_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NOT_UPLOADED")
    invoice_no: Mapped[str | None] = mapped_column(String(256), nullable=True)
    invoice_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sdms_check_head_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
