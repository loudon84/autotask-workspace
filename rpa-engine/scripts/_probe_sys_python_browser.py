import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    print("python", sys.executable)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://192.168.102.247:3000/", wait_until="domcontentloaded", timeout=20000)
            count = page.locator("img[data-rpa='login-captcha-image']").count()
            print("OK captcha=", count, "url=", page.url)
            browser.close()
            return 0
        except Exception as exc:  # noqa: BLE001
            print("FAIL", type(exc).__name__, str(exc)[:300])
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
