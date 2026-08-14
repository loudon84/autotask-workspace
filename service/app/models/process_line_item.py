from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProcessLineItem(BaseModel):
    __tablename__ = "process_line_items"
    __table_args__ = (
        UniqueConstraint(
            "instance_id",
            "line_number",
            name="uq_process_line_items_instance_line",
        ),
        Index("ix_process_line_items_instance_status", "instance_id", "line_status"),
    )

    instance_id: Mapped[str] = mapped_column(String(36), nullable=False)
    line_number: Mapped[str] = mapped_column(String(64), nullable=False)
    material_number: Mapped[str] = mapped_column(String(255), nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    item_specification: Mapped[str | None] = mapped_column(String(512), nullable=True)
    material_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    internal_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    order_quantity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_quantity_uom: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_selling_price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_included_amount: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    standard_delivery_days: Mapped[str | None] = mapped_column(String(32), nullable=True)
    meets_lead_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supplier_delivery_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outstanding_quantity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    direct_shipment_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_delivery_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    sub_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
