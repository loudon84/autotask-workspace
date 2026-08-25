from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from nodeskclaw_rpa_engine.runtime.errors import RpaFatalError
from nodeskclaw_rpa_engine.workers.schemas import BrowserSessionConfig

logger = logging.getLogger(__name__)

_LAUNCH_ATTEMPTS = 3
_LAUNCH_RETRY_DELAY_SECONDS = 0.8
_WINDOWS_CHROMIUM_ARGS = (
    "--disable-gpu",
    "--use-angle=swiftshader",
    "--disable-extensions",
    "--no-first-run",
)


def _has_bundled_chromium(root: Path) -> bool:
    if not root.is_dir():
        return False
    patterns = (
        "chromium-*/chrome-win*/chrome.exe",
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-mac*/Chromium",
    )
    return any(
        candidate.is_file()
        for pattern in patterns
        for candidate in root.glob(pattern)
    )


def ensure_playwright_browsers_path() -> str | None:
    """Drop unusable PLAYWRIGHT_BROWSERS_PATH values (empty sandbox dirs).

    Cursor agent shells may inject a TEMP playwright cache that does not exist
    or has no Chromium build. Playwright then fails to launch. Prefer a real
    local install.
    """
    current = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if current and _has_bundled_chromium(Path(current)):
        return current
    if current:
        os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        logger.warning(
            "Ignoring unusable PLAYWRIGHT_BROWSERS_PATH",
            extra={"configuredPath": current},
        )
    if os.name == "nt":
        fallback = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        if _has_bundled_chromium(fallback):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(fallback)
            return str(fallback)
    return None


@dataclass(slots=True)
class BrowserSession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    trace_started: bool
    _trace_stopped: bool = False

    async def stop_trace(self, path: Path) -> Path | None:
        if not self.trace_started or self._trace_stopped:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.tracing.stop(path=str(path))
        self._trace_stopped = True
        return path

    async def save_storage_state(self, path: Path) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await self.context.storage_state(path=str(path))

    async def close(self) -> None:
        if self.trace_started and not self._trace_stopped:
            try:
                await self.context.tracing.stop()
            except Exception:
                logger.warning("Browser trace stop failed during cleanup")
            self._trace_stopped = True
        for operation in (self.context.close, self.browser.close, self.playwright.stop):
            try:
                await operation()
            except Exception:
                logger.warning("Browser resource cleanup failed")


class ManagedBrowserSessionManager:
    def __init__(
        self,
        playwright_factory: Callable[[], Any] = async_playwright,
    ) -> None:
        self._playwright_factory = playwright_factory

    async def start(
        self,
        config: BrowserSessionConfig,
        *,
        run_directory: Path,
        trace_enabled: bool,
        storage_state: Path | None = None,
    ) -> BrowserSession:
        ensure_playwright_browsers_path()
        self._validate_config(config)
        await asyncio.to_thread(
            run_directory.mkdir,
            parents=True,
            exist_ok=True,
        )
        playwright: Playwright | None = None
        browser: Browser | None = None
        context: BrowserContext | None = None
        restored_state = storage_state
        if restored_state is not None:
            exists = await asyncio.to_thread(restored_state.is_file)
            if not exists:
                restored_state = None
        if config.channel in {"chrome", "msedge"}:
            logger.warning(
                "MANAGED sessions use bundled Chromium; ignoring branded channel",
                extra={"requestedChannel": config.channel},
            )
        last_exc: Exception | None = None
        try:
            playwright = await self._playwright_factory().start()
            for attempt in range(_LAUNCH_ATTEMPTS):
                state = restored_state if attempt == 0 else None
                try:
                    browser = await self._launch_bundled_chromium(
                        playwright,
                        config,
                        run_directory,
                    )
                    context = await self._open_context(browser, state)
                    if state is not None and context is None:
                        await asyncio.to_thread(state.unlink, missing_ok=True)
                        restored_state = None
                        try:
                            await browser.close()
                        except Exception:
                            logger.warning(
                                "Crashed browser could not be closed before relaunch"
                            )
                        browser = await self._launch_bundled_chromium(
                            playwright,
                            config,
                            run_directory,
                        )
                        context = await self._open_context(browser, None)
                    if context is None:
                        raise RuntimeError("browser context was not created")
                    if trace_enabled:
                        await context.tracing.start(
                            screenshots=True,
                            snapshots=True,
                            sources=True,
                        )
                    page = await context.new_page()
                    if restored_state is not None and state is not None:
                        logger.info(
                            "Portal session cache restored",
                            extra={"storageState": restored_state.name},
                        )
                    return BrowserSession(
                        playwright=playwright,
                        browser=browser,
                        context=context,
                        page=page,
                        trace_started=trace_enabled,
                    )
                except Exception as exc:
                    last_exc = exc
                    logger.exception(
                        "Managed browser launch failed",
                        extra={
                            "usedSessionCache": bool(state),
                            "attempt": attempt + 1,
                        },
                    )
                    for resource in (context, browser):
                        if resource is None:
                            continue
                        try:
                            await resource.close()
                        except Exception:
                            logger.warning("Browser cleanup failed after launch error")
                    browser = None
                    context = None
                    restored_state = None
                    if attempt + 1 < _LAUNCH_ATTEMPTS:
                        await asyncio.sleep(_LAUNCH_RETRY_DELAY_SECONDS)
            raise last_exc or RuntimeError("browser launch failed")
        except Exception as exc:
            if playwright is not None:
                await playwright.stop()
            cause = str(exc).strip()
            message = "Managed browser session could not be started"
            if cause:
                message = f"{message}: {cause[:400]}"
            raise RpaFatalError(
                "BROWSER_LAUNCH_FAILED",
                message,
            ) from exc

    @staticmethod
    async def _launch_bundled_chromium(
        playwright: Playwright,
        config: BrowserSessionConfig,
        run_directory: Path,
    ) -> Browser:
        options: dict[str, Any] = {
            "headless": config.headless,
            "channel": None,
            "downloads_path": str(run_directory / "downloads"),
        }
        if os.name == "nt":
            options["args"] = list(_WINDOWS_CHROMIUM_ARGS)
        return await playwright.chromium.launch(**options)

    @staticmethod
    async def _open_context(
        browser: Browser,
        storage_state: Path | None,
    ) -> BrowserContext | None:
        options: dict[str, Any] = {"accept_downloads": True}
        if storage_state is not None:
            options["storage_state"] = str(storage_state)
        try:
            return await browser.new_context(**options)
        except Exception:
            if storage_state is None:
                raise
            logger.warning(
                "Portal session cache could not be restored; starting empty",
                extra={"storageState": storage_state.name},
            )
            return None

    @staticmethod
    def _validate_config(config: BrowserSessionConfig) -> None:
        if config.mode != "MANAGED":
            raise RpaFatalError(
                "BROWSER_SESSION_MODE_UNSUPPORTED",
                "Only MANAGED browser sessions are supported",
            )
        if config.profile_ref is not None or config.cdp_endpoint_ref is not None:
            raise RpaFatalError(
                "BROWSER_SESSION_REFERENCE_FORBIDDEN",
                "MANAGED sessions cannot use Profile or CDP references",
            )
        if config.channel not in {"chromium", "chrome", "msedge"}:
            raise RpaFatalError(
                "BROWSER_CHANNEL_UNSUPPORTED",
                "Browser channel is not supported",
            )
        if config.close_policy not in {"ALWAYS", "CLOSE_ON_FINISH"}:
            raise RpaFatalError(
                "BROWSER_CLOSE_POLICY_UNSUPPORTED",
                "MANAGED sessions must close when the run finishes",
            )
