"""Per-login Playwright storage_state cache for MANAGED browser runs.

Identity is normalized portal URL + login username. The browser process still
closes after each Run; only cookies/localStorage are kept on disk.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_LOGIN_DROP_CODES = frozenset(
    {
        "SRM_LOGIN_FAILED",
        "SRM_CREDENTIALS_MISSING",
    }
)
_LOGIN_SKIP_PERSIST_CODES = frozenset(
    {
        "CAPTCHA_OCR_FAILED",
        "OCR_LENGTH_INVALID",
        "CAPTCHA_IMAGE_UNAVAILABLE",
        "CAPTCHA_OCR_UNAVAILABLE",
        "SRM_LOGIN_PAGE_UNAVAILABLE",
        "SRM_LOGIN_TIMEOUT",
    }
)


def normalize_portal_url(url: str) -> str:
    parsed = urlsplit((url or "").strip())
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()
    if not scheme or not hostname:
        return (url or "").strip().rstrip("/")
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))


def session_cache_key(portal_url: str, username: str) -> str:
    identity = f"{normalize_portal_url(portal_url)}\n{(username or '').strip()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def should_drop_session(error_code: str | None) -> bool:
    return (error_code or "") in _LOGIN_DROP_CODES


def should_persist_session(error_code: str | None) -> bool:
    if should_drop_session(error_code):
        return False
    return (error_code or "") not in _LOGIN_SKIP_PERSIST_CODES


class _ExclusiveFileLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: Any = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        if handle.tell() == 0:
            handle.write("lock\n")
            handle.flush()
        handle.seek(0)
        self._lock_handle(handle)
        self._file = handle

    def release(self) -> None:
        handle = self._file
        self._file = None
        if handle is None:
            return
        try:
            self._unlock_handle(handle)
        finally:
            handle.close()

    @staticmethod
    def _lock_handle(handle: Any) -> None:
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    return
                except OSError:
                    time.sleep(0.05)
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _unlock_handle(handle: Any) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class PortalSessionCache:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._locks: dict[str, asyncio.Lock] = {}
        self._meta = asyncio.Lock()

    def state_path(self, key: str) -> Path:
        return self._root / key / "storage_state.json"

    def existing_state_path(self, key: str | None) -> Path | None:
        if not key:
            return None
        path = self.state_path(key)
        return path if path.is_file() and path.stat().st_size > 0 else None

    @contextlib.asynccontextmanager
    async def lock(self, key: str | None) -> AsyncIterator[None]:
        if not key:
            yield
            return
        async with self._meta:
            in_process = self._locks.setdefault(key, asyncio.Lock())
        file_lock = _ExclusiveFileLock(self._root / key / ".lock")
        async with in_process:
            await asyncio.to_thread(file_lock.acquire)
            try:
                yield
            finally:
                await asyncio.to_thread(file_lock.release)

    def drop(self, key: str) -> None:
        path = self.state_path(key)
        path.unlink(missing_ok=True)
        logger.info("Portal session cache dropped", extra={"sessionCacheKey": key[:12]})

    async def persist(
        self,
        key: str,
        session: Any,
        *,
        portal_url: str,
        username: str,
    ) -> None:
        path = self.state_path(key)
        saver = getattr(session, "save_storage_state", None)
        if not callable(saver):
            return
        await saver(path)
        meta_path = path.parent / "meta.json"
        payload = {
            "portalUrl": normalize_portal_url(portal_url),
            "username": username.strip(),
        }
        await asyncio.to_thread(
            meta_path.write_text,
            json.dumps(payload, ensure_ascii=False, indent=2),
            "utf-8",
        )
        logger.info("Portal session cache saved", extra={"sessionCacheKey": key[:12]})
