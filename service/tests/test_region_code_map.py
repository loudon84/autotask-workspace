"""Region map validation before the table is migrated."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.models.user_cache import UserCache
from app.services.region_code_map_service import upsert_map


def _user() -> UserCache:
    return UserCache(
        user_id="user-1",
        name="客服",
        email="cs@example.com",
        current_org_id="tenant-1",
        org_role="member",
        synced_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_upsert_rejects_blank_code() -> None:
    with pytest.raises(BadRequestError) as exc_info:
        await upsert_map(
            MagicMock(),
            "tenant-1",
            category="BOE",
            region_code="  ",
            srm_display_name="台湾",
            actor=_user(),
        )
    assert exc_info.value.message_key == "errors.autotask.region_map_invalid"
