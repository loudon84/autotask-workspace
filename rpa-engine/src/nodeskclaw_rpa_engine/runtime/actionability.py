"""Check that a control would receive a click, without performing it.

Playwright ``click(trial=True)`` runs actionability (visible, enabled, stable,
not covered) and stops before the pointer down. Pair that with an
``elementFromPoint`` hit-test so frozen-column clones and overlays fail dry-run
instead of looking fine on a screenshot.
"""

from __future__ import annotations

from typing import Any

from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError

HIT_TEST_JS = r"""(el) => {
  if (!el) return { error: 'missing' };
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const top = document.elementFromPoint(cx, cy);
  const className = String(el.className || '');
  const hits = !!(top && (top === el || el.contains(top) || top.contains(el)));
  return {
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    disabledAttr: !!el.disabled,
    ariaDisabled: el.getAttribute('aria-disabled'),
    classDisabled: className.includes('is-disabled'),
    pointerEvents: style.pointerEvents,
    visibility: style.visibility,
    display: style.display,
    opacity: style.opacity,
    hitsSelf: hits,
    topTag: top ? top.tagName : null,
    topClass: top ? String(top.className || '').slice(0, 80) : null,
    topText: top ? String(top.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40) : null,
  };
}"""


def _first_line(exc: BaseException) -> str:
    return str(exc).split("\n", 1)[0].strip()[:240]


async def inspect_clickable(locator, *, timeout: int = 4000) -> dict[str, Any]:
    visible = False
    disabled = False
    try:
        visible = await locator.is_visible()
    except Exception:
        visible = False
    try:
        disabled = await locator.is_disabled()
    except Exception:
        disabled = False
    hit: dict[str, Any] | None = None
    try:
        hit = await locator.evaluate(HIT_TEST_JS)
    except Exception as exc:
        hit = {"error": type(exc).__name__, "message": _first_line(exc)}
    trial_ok = False
    trial_error = None
    try:
        await locator.click(timeout=timeout, trial=True)
        trial_ok = True
    except Exception as exc:
        trial_error = _first_line(exc)
    class_disabled = bool(isinstance(hit, dict) and hit.get("classDisabled"))
    hits_self = bool(isinstance(hit, dict) and hit.get("hitsSelf"))
    return {
        "visible": visible,
        "disabled": disabled or class_disabled,
        "hit": hit,
        "hitsSelf": hits_self,
        "trialOk": trial_ok,
        "trialError": trial_error,
    }


async def assert_clickable(
    locator,
    *,
    name: str,
    error_code: str = "CONTROL_UNCLICKABLE",
    timeout: int = 4000,
) -> dict[str, Any]:
    report = await inspect_clickable(locator, timeout=timeout)
    if report.get("trialOk") and not report.get("disabled"):
        return report
    reason = report.get("trialError") or "disabled or covered"
    raise RpaBusinessError(
        error_code,
        f"{name} is visible but not clickable ({reason})",
        details=report,
    )
