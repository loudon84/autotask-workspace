from collections.abc import Mapping

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOGIN_MARKERS = ("/login", "/captcha", "/auth", "/oauth", "/verify")
UPLOAD_MARKERS = ("/upload", "/scan", "/invoice", "/attach")


def is_dry_run(ctx) -> bool:
    config = getattr(ctx, "config", None)
    if isinstance(config, Mapping) and bool(config.get("dryRun") or config.get("dry_run")):
        return True
    raw = getattr(ctx, "input", None)
    return isinstance(raw, Mapping) and bool(raw.get("dryRun") or raw.get("dry_run"))


def should_block_write(
    method: str,
    url: str,
    *,
    allow_upload: bool = False,
    content_type: str | None = None,
) -> bool:
    verb = (method or "GET").upper()
    if verb not in WRITE_METHODS:
        return False
    target = (url or "").lower()
    if any(marker in target for marker in LOGIN_MARKERS):
        return False
    if allow_upload and any(marker in target for marker in UPLOAD_MARKERS):
        return False
    if allow_upload and "multipart" in (content_type or "").lower():
        return False
    return True


async def install_write_guard(page, *, dry_run: bool, allow_upload: bool = False) -> None:
    if not dry_run or page is None:
        return

    async def handler(route):
        request = route.request
        headers = request.headers or {}
        content_type = headers.get("content-type") or headers.get("Content-Type")
        if should_block_write(
            request.method,
            request.url,
            allow_upload=allow_upload,
            content_type=content_type,
        ):
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    await page.route("**/*", handler)
