import os

os.environ.setdefault("SKIP_AUTO_MIGRATE", "1")
os.environ.setdefault("SEED_DATA_ENABLED", "false")

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ConflictError
from app.main import app
from app.models.enums import WorkflowTemplateStatus
from app.models.user_cache import UserCache
from app.models.workflow_template import WorkflowTemplate
from app.services import workflow_template_service


class _ScalarResult:
    def __init__(self, value: str | None):
        self.value = value

    def scalar_one_or_none(self) -> str | None:
        return self.value


def _user() -> UserCache:
    return UserCache(
        user_id="user-001",
        name="测试用户",
        email="user@example.com",
        current_org_id="tenant-001",
        org_role="admin",
        portal_org_role=None,
        is_super_admin=False,
        synced_at=datetime.now(UTC),
    )


def _template(status: str) -> WorkflowTemplate:
    return WorkflowTemplate(
        id="template-001",
        tenant_id="tenant-001",
        name="测试流程模板",
        code="test_workflow",
        description=None,
        entity_type="CUSTOMER",
        category="test",
        status=status,
        version="1.0.0",
        input_schema="[]",
        business_steps="[]",
        created_by="user-001",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [WorkflowTemplateStatus.DRAFT.value, WorkflowTemplateStatus.DISABLED.value],
)
async def test_delete_unreferenced_draft_or_disabled_template(status: str) -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_ScalarResult(None), _ScalarResult(None)])
    db.commit = AsyncMock()
    template = _template(status)

    with (
        patch(
            "app.services.workflow_template_service.get_workflow_template",
            new=AsyncMock(return_value=template),
        ),
        patch(
            "app.services.workflow_template_service.audit_service.write_audit_log",
            new=AsyncMock(),
        ) as audit_write,
    ):
        await workflow_template_service.delete_workflow_template(
            db,
            "tenant-001",
            template.id,
            _user(),
        )

    assert template.deleted_at is not None
    db.commit.assert_awaited_once()
    audit_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_enabled_template_requires_disable_first() -> None:
    db = AsyncMock()
    template = _template(WorkflowTemplateStatus.ENABLED.value)

    with patch(
        "app.services.workflow_template_service.get_workflow_template",
        new=AsyncMock(return_value=template),
    ):
        with pytest.raises(ConflictError) as exc_info:
            await workflow_template_service.delete_workflow_template(
                db,
                "tenant-001",
                template.id,
                _user(),
            )

    assert exc_info.value.message_key == "errors.autotask.workflow_delete_requires_disabled"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_template_referenced_by_binding_is_blocked() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_ScalarResult("binding-001"))
    template = _template(WorkflowTemplateStatus.DISABLED.value)

    with patch(
        "app.services.workflow_template_service.get_workflow_template",
        new=AsyncMock(return_value=template),
    ):
        with pytest.raises(ConflictError) as exc_info:
            await workflow_template_service.delete_workflow_template(
                db,
                "tenant-001",
                template.id,
                _user(),
            )

    assert exc_info.value.message_key == "errors.autotask.workflow_delete_binding_referenced"
    assert exc_info.value.message == "模板已被 Binding 引用，只能禁用"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_template_referenced_by_historical_task_is_blocked() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_ScalarResult(None), _ScalarResult("task-001")])
    template = _template(WorkflowTemplateStatus.DRAFT.value)

    with patch(
        "app.services.workflow_template_service.get_workflow_template",
        new=AsyncMock(return_value=template),
    ):
        with pytest.raises(ConflictError) as exc_info:
            await workflow_template_service.delete_workflow_template(
                db,
                "tenant-001",
                template.id,
                _user(),
            )

    assert exc_info.value.message_key == "errors.autotask.workflow_delete_task_referenced"
    db.commit.assert_not_awaited()


def test_delete_workflow_template_api_returns_success_envelope() -> None:
    client = TestClient(app)

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    with patch(
        "app.api.workflow_templates.workflow_template_service.delete_workflow_template",
        new=AsyncMock(),
    ):
        response = client.delete(
            "/api/v1/autotask/workflow-templates/template-001",
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["data"] is None
    assert response.json()["message"] == "已删除"


def test_delete_workflow_template_api_exposes_binding_conflict() -> None:
    client = TestClient(app)

    async def override_user():
        return _user()

    async def override_db():
        yield AsyncMock()

    from app.core.deps import get_db
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    conflict = ConflictError(
        message="模板已被 Binding 引用，只能禁用",
        message_key="errors.autotask.workflow_delete_binding_referenced",
    )
    with patch(
        "app.api.workflow_templates.workflow_template_service.delete_workflow_template",
        new=AsyncMock(side_effect=conflict),
    ):
        response = client.delete(
            "/api/v1/autotask/workflow-templates/template-001",
            headers={"Authorization": "Bearer test-token"},
        )

    app.dependency_overrides.clear()
    assert response.status_code == 409
    assert response.json()["message_key"] == ("errors.autotask.workflow_delete_binding_referenced")
    assert response.json()["message"] == "模板已被 Binding 引用，只能禁用"
