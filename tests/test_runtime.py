import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from unittest import mock

from dsh_forge import runtime


class FakeResponse:
    def __init__(self, payload, url=runtime.RELEASE_API_URL):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.payload[:limit]


class RuntimeTests(unittest.TestCase):
    def test_packaged_version_is_read_from_bounded_build_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "build-version.json").write_text('{"version":"1.2.3-rc.1"}', encoding="utf-8")
            with mock.patch.object(runtime, "bundle_root", return_value=root):
                self.assertEqual(runtime.application_version(), "1.2.3-rc.1")
            (root / "build-version.json").write_text('{"version":"not-a-version"}', encoding="utf-8")
            with mock.patch.object(runtime, "bundle_root", return_value=root):
                self.assertEqual(runtime.application_version(), "development")

    def test_update_check_compares_semantic_versions_and_returns_only_official_link(self):
        seen = {}

        def open_release(request, timeout):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return FakeResponse({
                "tag_name": "v1.3.0",
                "html_url": "https://github.com/MichaelTheMay/dsh-forge/releases/tag/v1.3.0",
            })

        result = runtime.check_for_update("1.2.9", opener=open_release)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["latest_version"], "1.3.0")
        self.assertEqual(seen, {"url": runtime.RELEASE_API_URL, "timeout": 5})

        current = runtime.check_for_update("1.3.0-rc.1", opener=open_release)
        self.assertEqual(current["status"], "available")

    def test_update_check_fails_closed_on_unofficial_response(self):
        result = runtime.check_for_update(
            "1.0.0",
            opener=lambda *_args, **_kwargs: FakeResponse(
                {"tag_name": "v9.0.0", "html_url": "https://attacker.invalid/setup.exe"}
            ),
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["release_url"])

        redirected = runtime.check_for_update(
            "1.0.0",
            opener=lambda *_args, **_kwargs: FakeResponse({}, "https://attacker.invalid/latest"),
        )
        self.assertEqual(redirected["status"], "unavailable")

    def test_source_build_does_not_make_network_update_request(self):
        opener = mock.Mock()
        result = runtime.check_for_update("development", opener=opener)
        self.assertEqual(result["status"], "disabled")
        opener.assert_not_called()

    def test_windows_packaged_state_uses_local_app_data(self):
        with (
            mock.patch.object(runtime, "packaged", return_value=True),
            mock.patch.object(runtime.os, "name", "nt"),
            mock.patch.object(runtime.sys, "platform", "win32"),
            mock.patch.object(runtime, "Path", PureWindowsPath),
            mock.patch.object(runtime, "application_version", return_value="1.0.0"),
        ):
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}, clear=False):
                self.assertEqual(
                    runtime.default_state_root(),
                    PureWindowsPath(r"C:\Users\test\AppData\Local") / "DSH Forge",
                )
                status = runtime.application_status()
        self.assertEqual(status["platform"], "windows")
        self.assertFalse(status["native_sandbox"]["available"])
        self.assertIn("WSL2", status["native_sandbox"]["message"])

    def test_macos_packaged_state_uses_application_support(self):
        home = Path("/Users/test")
        with (
            mock.patch.object(runtime, "packaged", return_value=True),
            mock.patch.object(runtime.os, "name", "posix"),
            mock.patch.object(runtime.sys, "platform", "darwin"),
            mock.patch.object(runtime.Path, "home", return_value=home),
            mock.patch.object(runtime, "application_version", return_value="1.0.0"),
        ):
            self.assertEqual(
                runtime.default_state_root(),
                home / "Library" / "Application Support" / "DSH Forge",
            )
            status = runtime.application_status()
        self.assertEqual(status["platform"], "macos")
        self.assertFalse(status["native_sandbox"]["available"])
        self.assertIn("Linux host with Apptainer", status["native_sandbox"]["message"])


if __name__ == "__main__":
    unittest.main()
