# -*- coding: utf-8 -*-
"""把指定门户的 created_by 和 USER 授权转到目标用户。

默认只预览。加 --yes 才写库。不打印密码。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select

from app.core.deps import async_session_factory, engine as db_engine
from app.models.base import not_deleted
from app.models.enums import PortalPermission
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.services import audit_service
from app.services.json_utils import dumps_json

_CREATOR_PERMISSIONS = [
    PortalPermission.PORTAL_VIEW.value,
    PortalPermission.PORTAL_EDIT.value,
    PortalPermission.PORTAL_OPEN_WEB.value,
    PortalPermission.PORTAL_MANAGE_PERMISSION.value,
    PortalPermission.PORTAL_BIND_WORKFLOW.value,
    PortalPermission.PORTAL_VIEW_TASKS.value,
]


def _parse_perms(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


async def _user_by_name(db, name: str) -> UserCache:
    users = (
        await db.execute(select(UserCache).where(UserCache.name == name, not_deleted(UserCache)))
    ).scalars().all()
    if not users:
        raise SystemExit(f"找不到用户: {name}")
    if len(users) > 1:
        ids = ", ".join(u.user_id for u in users)
        raise SystemExit(f"用户名不唯一 {name}: {ids}")
    return users[0]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portal", default="天地伟业-芯云test")
    parser.add_argument("--from-name", default="苏宇威")
    parser.add_argument("--to-name", default="张站")
    parser.add_argument("--yes", action="store_true", help="写库；默认只预览")
    args = parser.parse_args()

    async with async_session_factory() as db:
        users = {
            u.user_id: u.name
            for u in (await db.execute(select(UserCache).where(not_deleted(UserCache)))).scalars().all()
        }
        portal = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.portal_name == args.portal,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        if portal is None:
            raise SystemExit(f"找不到门户: {args.portal}")

        from_user = await _user_by_name(db, args.from_name)
        to_user = await _user_by_name(db, args.to_name)
        current_owner = users.get(portal.created_by, portal.created_by)

        grants = (
            await db.execute(
                select(PortalAccessGrant).where(
                    PortalAccessGrant.portal_account_id == portal.id,
                    not_deleted(PortalAccessGrant),
                )
            )
        ).scalars().all()

        print(f"portal={portal.portal_name} id={portal.id}")
        print(f"created_by={portal.created_by} ({current_owner})")
        print("grants:")
        for g in grants:
            subject_name = users.get(g.subject_id, g.subject_id) if g.subject_type == "USER" else g.subject_id
            print(
                f"  {g.subject_type}={g.subject_id} ({subject_name}) "
                f"perms={_parse_perms(g.permissions)}"
            )

        if portal.created_by != from_user.user_id:
            raise SystemExit(
                f"当前 created_by 是 {current_owner}，不是 {args.from_name}，已中止"
            )

        existing_to = next(
            (
                g
                for g in grants
                if g.subject_type == "USER" and g.subject_id == to_user.user_id
            ),
            None,
        )
        from_grant = next(
            (
                g
                for g in grants
                if g.subject_type == "USER" and g.subject_id == from_user.user_id
            ),
            None,
        )

        print(
            f"plan: created_by {args.from_name} -> {args.to_name}; "
            f"{'update' if existing_to else 'create'} USER grant for {args.to_name}; "
            f"{'keep' if from_grant else 'no'} USER grant for {args.from_name}"
        )
        if not args.yes:
            print("preview only; pass --yes to apply")
            await db_engine.dispose()
            return 0

        portal.created_by = to_user.user_id
        if existing_to is None:
            db.add(
                PortalAccessGrant(
                    portal_account_id=portal.id,
                    subject_type="USER",
                    subject_id=to_user.user_id,
                    permissions=dumps_json(_CREATOR_PERMISSIONS),
                    granted_by=to_user.user_id,
                    granted_at=datetime.now(UTC).isoformat(),
                )
            )
        else:
            existing_to.permissions = dumps_json(_CREATOR_PERMISSIONS)

        await audit_service.write_audit_log(
            db,
            tenant_id=portal.tenant_id,
            actor_id=to_user.user_id,
            action=audit_service.ACTION_PORTAL_UPDATED,
            resource_type=audit_service.PORTAL_ACCOUNT_RESOURCE_TYPE,
            resource_id=portal.id,
            details={
                "changedFields": {
                    "created_by": {"from": from_user.user_id, "to": to_user.user_id}
                }
            },
        )
        await db.commit()
        print("applied")

    await db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
