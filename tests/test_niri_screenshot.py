import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from gradia.utils import niri_screenshot


class FakeEventStream:
    def __init__(self):
        read_fd, self.write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.emit({"ConfigLoaded": {"failed": False}})

    def emit(self, event):
        os.write(self.write_fd, (json.dumps(event) + "\n").encode())

    def terminate(self):
        os.close(self.write_fd)

    def wait(self, timeout=None):
        return 0


class NiriScreenshotTests(unittest.TestCase):
    def test_niri_backend_is_selected_only_in_niri_session(self):
        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "niri:GNOME"}), \
                patch.object(niri_screenshot.shutil, "which", return_value="/usr/bin/niri"):
            self.assertTrue(niri_screenshot.is_niri_session())

        with patch.dict(os.environ, {"XDG_CURRENT_DESKTOP": "GNOME"}), \
                patch.object(niri_screenshot.shutil, "which", return_value="/usr/bin/niri"):
            self.assertFalse(niri_screenshot.is_niri_session())

    def test_capture_uses_its_own_screenshot_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stream = FakeEventStream()
            opened = []

            def run_action(command, **_kwargs):
                path = Path(command[-1])
                path.write_bytes(b"\x89PNG\r\n\x1a\n")
                stream.emit({"ScreenshotCaptured": {"path": "/tmp/another-screenshot.png"}})
                stream.emit({"ScreenshotCaptured": {"path": str(path)}})
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(niri_screenshot.subprocess, "Popen", return_value=stream), \
                    patch.object(niri_screenshot.subprocess, "run", side_effect=run_action):
                path = niri_screenshot.capture_niri_screenshot(
                    screenshot_dir=Path(temp_dir), timeout=1,
                    on_ui_opened=lambda: opened.append(True),
                )

            self.assertEqual(Path(path).parent, Path(temp_dir))
            self.assertTrue(Path(path).is_file())
            self.assertEqual(opened, [True])

    def test_clipboard_only_capture_reports_how_to_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            stream = FakeEventStream()

            def run_action(command, **_kwargs):
                stream.emit({"ScreenshotCaptured": {"path": None}})
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch.object(niri_screenshot.subprocess, "Popen", return_value=stream), \
                    patch.object(niri_screenshot.subprocess, "run", side_effect=run_action):
                with self.assertRaisesRegex(niri_screenshot.NiriScreenshotError, "Press Enter"):
                    niri_screenshot.capture_niri_screenshot(
                        screenshot_dir=Path(temp_dir), timeout=1
                    )


if __name__ == "__main__":
    unittest.main()
