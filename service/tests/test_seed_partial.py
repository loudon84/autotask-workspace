"""Tests for idempotent / schema-tolerant seed."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import ProgrammingError

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from app.startup import seed as seed_mod


@pytest.mark.asyncio
async def test_seed_group_skips_missing_table():
    db = AsyncMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    db.begin_nested = MagicMock(return_value=nested)

    async def boom():
        raise ProgrammingError(
            "SELECT",
            {},
            Exception('relation "portal_accounts" does not exist'),
        )

    inserted, skipped = await seed_mod._seed_group(db, "portal_accounts", boom)
    assert inserted == 0
    assert skipped == 0


@pytest.mark.asyncio
async def test_exists_by_id_false_when_empty():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    assert await seed_mod._exists_by_id(db, seed_mod.PortalAccount, "portal-001") is False


@pytest.mark.asyncio
async def test_exists_by_id_true_when_found():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = "portal-001"
    db.execute = AsyncMock(return_value=result)

    assert await seed_mod._exists_by_id(db, seed_mod.PortalAccount, "portal-001") is True


@pytest.mark.asyncio
async def test_seed_portal_accounts_skips_existing_ids():
    db = AsyncMock()

    async def exists_side_effect(_db, _model, entity_id):
        return entity_id == "portal-001"

    sample = [
        {
            "id": "portal-001",
            "entityType": "CUSTOMER",
            "erpEntityCode": "C1",
            "erpEntityName": "A",
            "portalName": "P",
            "portalUrl": "https://portal.example.com",
            "loginAccount": "a@example.com",
        },
        {
            "id": "portal-002",
            "entityType": "CUSTOMER",
            "erpEntityCode": "C2",
            "erpEntityName": "B",
            "portalName": "Q",
            "portalUrl": "https://portal-b.example.com",
            "loginAccount": "b@example.com",
        },
    ]

    with (
        patch.object(seed_mod, "_load_json", return_value=sample),
        patch.object(seed_mod, "_exists_by_id", side_effect=exists_side_effect),
    ):
        inserted, skipped = await seed_mod._seed_portal_accounts(db)

    assert inserted == 1
    assert skipped == 1
    assert db.add.call_count == 1


@pytest.mark.asyncio
async def test_run_seed_commits_and_survives_group_skip():
    session = AsyncMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)

    with patch.object(seed_mod, "_seed_portal_accounts", AsyncMock(return_value=(1, 0))):
        with patch.object(seed_mod, "_seed_portal_access_grants", AsyncMock(return_value=(0, 1))):
            with patch.object(seed_mod, "_seed_workflow_templates", AsyncMock(return_value=(0, 0))):
                with patch.object(seed_mod, "_seed_workflow_bindings", AsyncMock(return_value=(0, 0))):
                    with patch.object(seed_mod, "_seed_tasks", AsyncMock(return_value=(0, 0))):
                        with patch.object(seed_mod, "_seed_task_runs", AsyncMock(return_value=(0, 0))):
                            with patch.object(seed_mod, "_seed_workers", AsyncMock(return_value=(0, 0))):
                                with patch.object(seed_mod, "_seed_artifacts", AsyncMock(return_value=(0, 0))):
                                    with patch.object(seed_mod, "_seed_components", AsyncMock(return_value=(0, 0))):
                                        with patch.object(seed_mod, "_seed_settings", AsyncMock(return_value=(0, 0))):
                                            with patch.object(seed_mod, "_seed_audit_logs", AsyncMock(return_value=(0, 0))):
                                                await seed_mod.run_seed(factory)

    session.commit.assert_awaited()
