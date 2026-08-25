from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from nodeskclaw_rpa_engine.runtime.browser import (
    ManagedBrowserSessionManager,
    ensure_playwright_browsers_path,
)
from nodeskclaw_rpa_engine.runtime import browser as browser_mod
from nodeskclaw_rpa_engine.runtime.errors import RpaFatalError
from nodeskclaw_rpa_engine.workers.schemas import BrowserSessionConfig


class FakeTracing:
    def __init__(self) -> None:
        self.started = False
        self.stopped: str | None = None

    async def start(self, **_kwargs) -> None:
        self.started = True

    async def stop(self, *, path: str | None = None) -> None:
        self.stopped = path or "discarded"


class FakeContext:
    def __init__(self) -> None:
        self.tracing = FakeTracing()
        self.closed = False
        self.page = object()

    async def new_page(self):
        return self.page

    async def close(self) -> None:
        self.closed = True

    async def storage_state(self, *, path: str) -> None:
        await asyncio.to_thread(
            Path(path).write_text,
            '{"cookies":[],"origins":[]}',
            encoding="utf-8",
        )


class FakeBrowser:
    def __init__(self) -> None:
        self.context = FakeContext()
        self.closed = False
        self.context_options: dict[str, object] = {}

    async def new_context(self, **kwargs):
        self.context_options = kwargs
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self) -> None:
        self.browser = FakeBrowser()
        self.launch_options: dict[str, object] = {}

    async def launch(self, **kwargs):
        self.launch_options = kwargs
        return self.browser


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakeController:
    def __init__(self) -> None:
        self.playwright = FakePlaywright()

    async def start(self):
        return self.playwright


class FallingBrandedChromium(FakeChromium):
    async def launch(self, **kwargs):
        if kwargs.get("channel") in {"chrome", "msedge"}:
            raise RuntimeError("Target crashed")
        return await super().launch(**kwargs)


class FallingBrandedController(FakeController):
    def __init__(self) -> None:
        super().__init__()
        self.playwright.chromium = FallingBrandedChromium()


def config(**updates: object) -> BrowserSessionConfig:
    values = {
        "mode": "MANAGED",
        "headless": True,
        "channel": "chromium",
        "profile_ref": None,
        "cdp_endpoint_ref": None,
        "close_policy": "CLOSE_ON_FINISH",
    }
    values.update(updates)
    return BrowserSessionConfig(**values)


def expected_launch_options(tmp_path: Path) -> dict[str, object]:
    options: dict[str, object] = {
        "headless": True,
        "channel": None,
        "downloads_path": str(tmp_path / "downloads"),
    }
    if os.name == "nt":
        options["args"] = [
            "--disable-gpu",
            "--use-angle=swiftshader",
            "--disable-extensions",
            "--no-first-run",
        ]
    return options


async def test_managed_browser_owns_context_page_trace_and_cleanup(tmp_path) -> None:
    controller = FakeController()
    manager = ManagedBrowserSessionManager(lambda: controller)

    session = await manager.start(
        config(),
        run_directory=tmp_path,
        trace_enabled=True,
    )
    trace_path = tmp_path / "trace.zip"
    await session.stop_trace(trace_path)
    await session.close()

    playwright = controller.playwright
    assert playwright.chromium.launch_options == expected_launch_options(tmp_path)
    assert playwright.chromium.browser.context_options == {
        "accept_downloads": True
    }
    assert playwright.chromium.browser.context.tracing.started is True
    assert playwright.chromium.browser.context.tracing.stopped == str(trace_path)
    assert playwright.chromium.browser.context.closed is True
    assert playwright.chromium.browser.closed is True
    assert playwright.stopped is True


async def test_managed_browser_falls_back_to_chromium_when_branded_channel_fails(
    tmp_path: Path,
) -> None:
    controller = FallingBrandedController()
    manager = ManagedBrowserSessionManager(lambda: controller)

    session = await manager.start(
        config(channel="chrome"),
        run_directory=tmp_path,
        trace_enabled=False,
    )
    await session.close()

    assert controller.playwright.chromium.launch_options["channel"] is None


class RestoreFailingBrowser(FakeBrowser):
    async def new_context(self, **kwargs):
        self.context_options = kwargs
        if "storage_state" in kwargs:
            raise RuntimeError("Target crashed")
        return self.context


class RestoreFailingChromium(FakeChromium):
    def __init__(self) -> None:
        super().__init__()
        self.launch_count = 0

    async def launch(self, **kwargs):
        self.launch_count += 1
        self.launch_options = kwargs
        self.browser = RestoreFailingBrowser()
        return self.browser


class RestoreFailingController(FakeController):
    def __init__(self) -> None:
        super().__init__()
        self.playwright.chromium = RestoreFailingChromium()


async def test_managed_browser_relaunches_after_storage_state_restore_fails(
    tmp_path: Path,
) -> None:
    controller = RestoreFailingController()
    manager = ManagedBrowserSessionManager(lambda: controller)
    state = tmp_path / "storage_state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    session = await manager.start(
        config(),
        run_directory=tmp_path / "run",
        trace_enabled=False,
        storage_state=state,
    )
    await session.close()

    assert controller.playwright.chromium.launch_count == 2
    assert "storage_state" not in controller.playwright.chromium.browser.context_options
    assert not state.is_file()


async def test_managed_browser_restores_and_saves_storage_state(tmp_path: Path) -> None:
    controller = FakeController()
    manager = ManagedBrowserSessionManager(lambda: controller)
    state = tmp_path / "storage_state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    session = await manager.start(
        config(),
        run_directory=tmp_path / "run",
        trace_enabled=False,
        storage_state=state,
    )
    saved = tmp_path / "saved.json"
    await session.save_storage_state(saved)
    await session.close()

    assert controller.playwright.chromium.browser.context_options == {
        "accept_downloads": True,
        "storage_state": str(state),
    }
    assert saved.is_file()


@pytest.mark.parametrize("channel", ["chrome", "msedge"])
async def test_managed_browser_ignores_branded_channel(
    tmp_path: Path,
    channel: str,
) -> None:
    controller = FakeController()
    manager = ManagedBrowserSessionManager(lambda: controller)

    session = await manager.start(
        config(channel=channel),
        run_directory=tmp_path,
        trace_enabled=False,
    )
    await session.close()

    assert controller.playwright.chromium.launch_options["channel"] is None


class FlakyLaunchChromium(FakeChromium):
    def __init__(self, fail_times: int) -> None:
        super().__init__()
        self.fail_times = fail_times
        self.launch_count = 0

    async def launch(self, **kwargs):
        self.launch_count += 1
        self.launch_options = kwargs
        if self.launch_count <= self.fail_times:
            raise RuntimeError("Browser.new_page: Target crashed")
        self.browser = FakeBrowser()
        return self.browser


class FlakyLaunchController(FakeController):
    def __init__(self, fail_times: int) -> None:
        super().__init__()
        self.playwright.chromium = FlakyLaunchChromium(fail_times)


async def test_managed_browser_retries_transient_target_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def instant_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(browser_mod.asyncio, "sleep", instant_sleep)
    controller = FlakyLaunchController(fail_times=2)
    manager = ManagedBrowserSessionManager(lambda: controller)

    session = await manager.start(
        config(),
        run_directory=tmp_path,
        trace_enabled=False,
    )
    await session.close()

    assert controller.playwright.chromium.launch_count == 3
    assert sleeps == [0.8, 0.8]


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"mode": "CDP_ATTACH"}, "BROWSER_SESSION_MODE_UNSUPPORTED"),
        ({"profile_ref": "profile-1"}, "BROWSER_SESSION_REFERENCE_FORBIDDEN"),
        ({"cdp_endpoint_ref": "cdp-1"}, "BROWSER_SESSION_REFERENCE_FORBIDDEN"),
        ({"channel": "firefox"}, "BROWSER_CHANNEL_UNSUPPORTED"),
        ({"close_policy": "KEEP_OPEN"}, "BROWSER_CLOSE_POLICY_UNSUPPORTED"),
    ],
)
async def test_managed_browser_rejects_unsupported_configuration(
    tmp_path: Path,
    updates: dict[str, object],
    code: str,
) -> None:
    manager = ManagedBrowserSessionManager(lambda: FakeController())
    with pytest.raises(RpaFatalError) as captured:
        await manager.start(
            config(**updates),
            run_directory=tmp_path,
            trace_enabled=False,
        )
    assert captured.value.code == code


def test_ensure_playwright_ignores_missing_browser_path(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "cursor-sandbox-playwright"
    fallback = tmp_path / "ms-playwright"
    chromium = fallback / "chromium-1" / "chrome-win64"
    chromium.mkdir(parents=True)
    (chromium / "chrome.exe").write_bytes(b"")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(missing))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = ensure_playwright_browsers_path()
    assert result == str(fallback)
    assert Path(result).is_dir()


def test_ensure_playwright_keeps_existing_browser_path(monkeypatch, tmp_path: Path) -> None:
    existing = tmp_path / "real-browsers"
    chromium = existing / "chromium-1" / "chrome-win64"
    chromium.mkdir(parents=True)
    (chromium / "chrome.exe").write_bytes(b"")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(existing))
    assert ensure_playwright_browsers_path() == str(existing)


def test_ensure_playwright_ignores_empty_browser_path(monkeypatch, tmp_path: Path) -> None:
    empty = tmp_path / "cursor-sandbox-playwright"
    empty.mkdir()
    fallback = tmp_path / "ms-playwright"
    chromium = fallback / "chromium-1" / "chrome-win64"
    chromium.mkdir(parents=True)
    (chromium / "chrome.exe").write_bytes(b"")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(empty))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    result = ensure_playwright_browsers_path()
    assert result == str(fallback)
