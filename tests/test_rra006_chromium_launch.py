"""`launch_chromium` must apply the launch flag `KHEPRI-DEC-007` requires.

No browser is downloaded or started here. The observable contract is the argument list handed to
Playwright, so a fake playwright records it and the assertions read it back. That keeps this test
runnable in the same constrained checkout the rest of the PDF surface is verified in --
`chromium.py` is deliberately imported by nothing else in the package for exactly that reason.
"""

from __future__ import annotations

from typing import Any

import pytest

from khepri.rra.rendering import chromium
from khepri.rra.rendering.chromium import LAUNCH_ARGS, launch_chromium


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.browser = FakeBrowser()

    def launch(self, **kwargs: Any) -> FakeBrowser:
        self.calls.append(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()

    def __enter__(self) -> FakePlaywright:
        return self

    def __exit__(self, *_: object) -> None:
        return None


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakePlaywright:
    play = FakePlaywright()
    monkeypatch.setattr(chromium, "sync_playwright", lambda: play)
    return play


class TestTheRequiredLaunchFlag:
    def test_disable_dev_shm_usage_is_passed(self, fake: FakePlaywright) -> None:
        """KHEPRI-DEC-007 calls this a correctness requirement, not a tuning flag.

        Fargate fixes /dev/shm at 64 MiB and does not support sharedMemorySize, so without
        this flag Chromium exceeds it while printing and fails as a renderer crash rather
        than as the memory limit it is.
        """
        with launch_chromium():
            pass

        assert len(fake.chromium.calls) == 1
        assert "--disable-dev-shm-usage" in fake.chromium.calls[0]["args"]

    def test_the_call_uses_the_module_constant(self, fake: FakePlaywright) -> None:
        """Named against LAUNCH_ARGS so the flag cannot drift from what the code applies."""
        with launch_chromium():
            pass

        assert fake.chromium.calls[0]["args"] == list(LAUNCH_ARGS)

    def test_the_constant_is_immutable(self) -> None:
        """A list would let one caller mutate every later launch."""
        assert isinstance(LAUNCH_ARGS, tuple)

    def test_a_fresh_list_is_handed_over_each_launch(self, fake: FakePlaywright) -> None:
        """Playwright receives a list; it must not be one shared object callers can mutate."""
        with launch_chromium():
            pass
        first = fake.chromium.calls[0]["args"]
        first.append("--not-ours")

        with launch_chromium():
            pass

        assert fake.chromium.calls[1]["args"] == list(LAUNCH_ARGS)


class TestTheBrowserLifecycleIsUnchanged:
    def test_headless_is_still_the_default(self, fake: FakePlaywright) -> None:
        with launch_chromium():
            pass

        assert fake.chromium.calls[0]["headless"] is True

    def test_headless_can_still_be_overridden(self, fake: FakePlaywright) -> None:
        with launch_chromium(headless=False):
            pass

        assert fake.chromium.calls[0]["headless"] is False

    def test_the_browser_is_closed_even_when_the_body_raises(
        self, fake: FakePlaywright
    ) -> None:
        with pytest.raises(RuntimeError), launch_chromium():
            raise RuntimeError("printing failed")

        assert fake.chromium.browser.closed is True
