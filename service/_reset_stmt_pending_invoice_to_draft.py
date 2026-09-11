"""Reset one UNCHECKED statement bill back to DRAFT / 待生成.

Reads DATABASE_URL from service/.env.product only. Does not touch 测库.
Does not call SRM; the wrong portal statement must be voided there separately.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import not_deleted
from app.models.enums import ProcessInstanceStatus, ProcessStage
from app.models.process_instance import ProcessInstance
from app.models.statement_bill import StatementBill
from app.services import process_instance_service as process_svc
from app.services.json_utils import loads_json

PRODUCT_ENV = Path(r"d:\work_space260811\autotask-workspace\service\.env.product")
CHECK_DATE = date(2026, 9, 11)
CHECK_AMOUNT = Decimal("12324564.52")


def load_product_database_url() -> str:
    for line in PRODUCT_ENV.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key == "DATABASE_URL":
            return value.strip().strip('"').strip("'")
    raise SystemExit("DATABASE_URL missing in .env.product")


def db_host_name(url: str) -> str:
    return url.split("@")[-1].split("?")[0]


async def main(*, yes: bool) -> None:
    db_url = load_product_database_url()
    db = db_host_name(db_url)
    print("using_db", db)
    if "rpa_autotask" not in db:
        raise SystemExit("refusing: .env.product is not rpa_autotask")

    engine = create_async_engine(db_url, echo=False, connect_args={"ssl": False})
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            bills = (
                await session.execute(
                    select(StatementBill, ProcessInstance)
                    .join(
                        ProcessInstance,
                        ProcessInstance.id == StatementBill.process_instance_id,
                    )
                    .where(
                        StatementBill.check_date == CHECK_DATE,
                        StatementBill.check_amount == CHECK_AMOUNT,
                        not_deleted(StatementBill),
                        not_deleted(ProcessInstance),
                    )
                )
            ).all()
            if len(bills) != 1:
                raise SystemExit(f"expected exactly 1 bill, got {len(bills)}")
            bill, instance = bills[0]
            summary = loads_json(instance.summary, {})
            lines = summary.get("lines") if isinstance(summary, dict) else None
            line_count = len(lines) if isinstance(lines, list) else 0
            print(
                "bill",
                bill.id,
                bill.check_status,
                instance.stage,
                instance.status,
                "lines",
                line_count,
            )
            if bill.check_status != "UNCHECKED":
                raise SystemExit(f"refusing status {bill.check_status}")
            if instance.stage != ProcessStage.STMT_PENDING_INVOICE.value:
                raise SystemExit(f"refusing stage {instance.stage}")
            if line_count < 1:
                raise SystemExit("summary.lines missing; cannot retry generate later")
            if not yes:
                print("preview only; pass --yes to reset to DRAFT / STMT_GENERATING")
                return
            bill.check_status = "DRAFT"
            bill.invoice_status = "NOT_UPLOADED"
            bill.invoice_no = None
            bill.invoice_amount = None
            bill.last_error = None
            instance.status = ProcessInstanceStatus.ACTIVE.value
            instance.last_error_code = None
            instance.last_error_message = None
            process_svc._change_stage(
                session,
                instance,
                ProcessStage.STMT_GENERATING,
                actor="ops",
                note="reset wrong 10-line generate back to 待生成",
            )
            await session.commit()
            print("reset", bill.id, "DRAFT", instance.stage)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(yes=args.yes))
