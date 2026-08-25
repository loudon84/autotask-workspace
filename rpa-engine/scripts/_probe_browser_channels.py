import os
import sys

from playwright.sync_api import sync_playwright

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")


def try_launch(label: str, **kwargs) -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, **kwargs)
            page = browser.new_page()
            page.goto("http://192.168.102.247:3000/", wait_until="domcontentloaded", timeout=20000)
            count = page.locator("img[data-rpa='login-captcha-image']").count()
            print(label, "OK captcha=", count, "url=", page.url)
            browser.close()
        except Exception as exc:  # noqa: BLE001
            print(label, "FAIL", type(exc).__name__, str(exc)[:160])


def main() -> int:
    # Engine maps channel=chromium to channel=None
    try_launch("engine-chromium(None)")
    try_launch("chrome", channel="chrome")
    try_launch("headless-shell", channel="chromium-headless-shell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
