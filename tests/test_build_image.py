"""`build_image` must refuse rather than report a fact it could not read.

Docker is not available in CI, so nothing here builds an image. What is verifiable without a daemon
is the refusal behaviour and the digest arithmetic, and those are exactly the parts that would
otherwise let a partial or invented fact set reach the environment descriptor.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from scripts import build_image
from scripts.build_image import BuildRefused


class TestItRefusesWithoutDocker:
    def test_a_missing_docker_binary_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A descriptor with three of four fields is not a descriptor."""
        monkeypatch.setattr(build_image.shutil, "which", lambda _: None)

        with pytest.raises(BuildRefused, match="docker is not on PATH"):
            build_image._docker()

    def test_main_returns_nonzero_rather_than_printing_partial_facts(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(build_image.shutil, "which", lambda _: None)

        code = build_image.main(["--skip-build"])

        assert code == 1
        assert "REFUSED" in capsys.readouterr().err


class TestTheLockfileDigest:
    def test_it_is_the_sha256_of_the_real_lockfile(self) -> None:
        expected = hashlib.sha256(build_image.LOCKFILE.read_bytes()).hexdigest()

        assert build_image.lockfile_digest() == f"sha256:{expected}"

    def test_a_missing_lockfile_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build_image, "LOCKFILE", Path("does-not-exist.lock"))

        with pytest.raises(BuildRefused, match="uv.lock digest cannot be computed"):
            build_image.lockfile_digest()


class TestTheImageDigest:
    def test_a_pushed_repo_digest_is_preferred(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The descriptor means the registry digest, not the local config blob ID."""
        monkeypatch.setattr(
            build_image,
            "_inspect",
            lambda _tag: {
                "RepoDigests": ["example/khepri@sha256:" + "ab" * 32],
                "Id": "sha256:" + "cd" * 32,
            },
        )

        assert build_image.image_digest("t") == "sha256:" + "ab" * 32

    def test_the_local_id_is_used_when_nothing_is_pushed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            build_image,
            "_inspect",
            lambda _tag: {"RepoDigests": [], "Id": "sha256:" + "cd" * 32},
        )

        assert build_image.image_digest("t") == "sha256:" + "cd" * 32


class TestChromiumFactParsing:
    def test_a_revision_and_version_are_split(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(build_image, "_in_image", lambda _t, _c: "1228 149.0.7827.55")

        assert build_image.chromium_facts("t") == ("1228", "149.0.7827.55")

    @pytest.mark.parametrize("output", ["", "1228", "1228 149.0 extra"])
    def test_unexpected_output_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, output: str
    ) -> None:
        """Guessing a browser version would put an unverified fact in a governed document."""
        monkeypatch.setattr(build_image, "_in_image", lambda _t, _c: output)

        with pytest.raises(BuildRefused, match="could not read Chromium"):
            build_image.chromium_facts("t")


class TestCollectRefusesPartialResults:
    def _stub(self, monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
        defaults = {
            "image_digest": "sha256:" + "ab" * 32,
            "python_patch_version": "3.13.12",
            "playwright_version": "1.61.0",
        }
        defaults.update(overrides)
        for name, value in defaults.items():
            monkeypatch.setattr(build_image, name, lambda _tag, _v=value: _v)
        monkeypatch.setattr(build_image, "chromium_facts", lambda _tag: ("1228", "149.0.7827.55"))

    def test_a_complete_set_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stub(monkeypatch)

        facts = build_image.collect("t")

        assert facts["python_patch_version"] == "3.13.12"
        assert facts["chromium_revision"] == "1228"
        assert facts["uv_lock_sha256"].startswith("sha256:")

    def test_one_blank_fact_refuses_the_whole_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._stub(monkeypatch, python_patch_version="")

        with pytest.raises(BuildRefused, match="partial fact set"):
            build_image.collect("t")


class TestTheRenderedOutput:
    def test_it_states_that_the_template_digest_is_absent(self) -> None:
        """The fourth descriptor fact comes from synthesis; silence would imply it was covered."""
        rendered = build_image.render({"oci_image_digest": "sha256:x"})

        assert "synthesized-template SHA-256 is NOT here" in rendered
        assert "oci_image_digest" in rendered
