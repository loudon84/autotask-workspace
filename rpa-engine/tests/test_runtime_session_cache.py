from __future__ import annotations

import asyncio
import json
from pathlib import Path

from nodeskclaw_rpa_engine.runtime.session_cache import (
    PortalSessionCache,
    normalize_portal_url,
    session_cache_key,
    should_drop_session,
    should_persist_session,
)


def test_normalize_portal_url_strips_hash_slash_and_default_port() -> None:
    assert (
        normalize_portal_url("http://192.168.102.247:3000/#/login")
        == "http://192.168.102.247:3000"
    )
    assert (
        normalize_portal_url("https://supplier.tiandy.com/")
        == "https://supplier.tiandy.com"
    )
    assert (
        normalize_portal_url("https://supplier.tiandy.com:443/app/")
        == "https://supplier.tiandy.com/app"
    )


def test_session_cache_key_splits_url_and_login() -> None:
    demo = "http://192.168.102.247:3000"
    official = "https://supplier.tiandy.com"
    same_demo = session_cache_key(f"{demo}/", "02556")
    hashed_demo = session_cache_key(f"{demo}/#/dashboard", "02556")
    other_login = session_cache_key(demo, "other")
    official_key = session_cache_key(official, "02556")

    assert same_demo == hashed_demo
    assert same_demo != other_login
    assert same_demo != official_key
    assert "02556" not in same_demo
    assert demo not in same_demo


def test_persist_and_drop_rules() -> None:
    assert should_persist_session(None) is True
    assert should_persist_session("PO_NOT_FOUND") is True
    assert should_persist_session("CAPTCHA_OCR_FAILED") is False
    assert should_persist_session("SRM_LOGIN_FAILED") is False
    assert should_drop_session("SRM_LOGIN_FAILED") is True
    assert should_drop_session("CAPTCHA_OCR_FAILED") is False


class _Session:
    async def save_storage_state(self, path: Path) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(
            path.write_text,
            '{"cookies":[],"origins":[]}',
            encoding="utf-8",
        )


async def test_session_cache_lock_serializes_same_key(tmp_path: Path) -> None:
    cache = PortalSessionCache(tmp_path)
    order: list[int] = []

    async def hold(marker: int) -> None:
        async with cache.lock("same-key"):
            order.append(marker)
            await asyncio.sleep(0.05)
            order.append(marker)

    await asyncio.gather(hold(1), hold(2))
    assert order in ([1, 1, 2, 2], [2, 2, 1, 1])


async def test_session_cache_persist_writes_meta_without_password(
    tmp_path: Path,
) -> None:
    cache = PortalSessionCache(tmp_path)
    key = session_cache_key("http://mock.test/", "portal-user")
    await cache.persist(
        key,
        _Session(),
        portal_url="http://mock.test/#/login",
        username="portal-user",
    )
    state = cache.existing_state_path(key)
    assert state is not None
    meta = json.loads((state.parent / "meta.json").read_text(encoding="utf-8"))
    assert meta == {"portalUrl": "http://mock.test", "username": "portal-user"}
