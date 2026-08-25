"""SDMS 对账单发票附件上传（HTTP）。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import sdms_attachment_client as client


@pytest.mark.asyncio
async def test_upload_requires_check_num() -> None:
    message = await client.upload_statement_invoices_to_sdms(
        check_num="",
        username="S01",
        file_paths=["a.pdf"],
    )
    assert message is not None
    assert "对账单号" in message


@pytest.mark.asyncio
async def test_upload_requires_username() -> None:
    message = await client.upload_statement_invoices_to_sdms(
        check_num="104DZ26080001",
        username="",
        file_paths=["a.pdf"],
    )
    assert message is not None
    assert "工号" in message


@pytest.mark.asyncio
async def test_upload_posts_multipart(tmp_path: Path) -> None:
    invoice = tmp_path / "inv.pdf"
    invoice.write_bytes(b"%PDF-1.4 test")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": "200", "data": {}}
    mock_http = MagicMock()
    mock_http.post = AsyncMock(return_value=mock_resp)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.sdms_attachment_client.httpx.AsyncClient", return_value=mock_http):
        message = await client.upload_statement_invoices_to_sdms(
            check_num="104DZ26080001",
            username="S01",
            file_paths=[str(invoice)],
        )

    assert message is None
    kwargs = mock_http.post.await_args.kwargs
    assert kwargs["data"]["flag"] == "SDMS_ARR"
    assert kwargs["data"]["order_number"] == "104DZ26080001"
    assert kwargs["data"]["username"] == "S01"
    assert kwargs["files"]["file"][0] == "inv.pdf"
