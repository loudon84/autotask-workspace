import pytest

from nodeskclaw_rpa_engine.runtime.actionability import assert_clickable, inspect_clickable
from nodeskclaw_rpa_engine.runtime.errors import RpaBusinessError


class FakeLocator:
    def __init__(self, *, visible=True, disabled=False, trial_error=None, hit=None):
        self.visible = visible
        self.disabled = disabled
        self.trial_error = trial_error
        self.hit = hit or {
            "width": 80,
            "height": 28,
            "disabledAttr": disabled,
            "classDisabled": disabled,
            "pointerEvents": "none" if disabled else "auto",
            "hitsSelf": not disabled,
        }
        self.clicks = []

    async def is_visible(self):
        return self.visible

    async def is_disabled(self):
        return self.disabled

    async def evaluate(self, _js):
        return self.hit

    async def click(self, timeout=0, trial=False):
        if trial:
            if self.trial_error:
                raise TimeoutError(self.trial_error)
            if self.disabled:
                raise TimeoutError("element is not enabled")
            return
        self.clicks.append("real")


@pytest.mark.asyncio
async def test_inspect_clickable_reports_trial_ok():
    report = await inspect_clickable(FakeLocator())
    assert report["trialOk"] is True
    assert report["disabled"] is False
    assert report["hitsSelf"] is True


@pytest.mark.asyncio
async def test_assert_clickable_rejects_disabled():
    with pytest.raises(RpaBusinessError) as caught:
        await assert_clickable(
            FakeLocator(disabled=True),
            name="提交审核",
            error_code="SRM_STMT_SUBMIT_UNCLICKABLE",
        )
    assert caught.value.code == "SRM_STMT_SUBMIT_UNCLICKABLE"


@pytest.mark.asyncio
async def test_assert_clickable_rejects_covered_control():
    locator = FakeLocator(trial_error="intercepts pointer events")
    locator.hit["hitsSelf"] = False
    with pytest.raises(RpaBusinessError) as caught:
        await assert_clickable(locator, name="提交审核")
    assert "not clickable" in caught.value.safe_message


@pytest.mark.asyncio
async def test_assert_clickable_does_not_perform_real_click():
    locator = FakeLocator()
    await assert_clickable(locator, name="提交审核")
    assert locator.clicks == []
