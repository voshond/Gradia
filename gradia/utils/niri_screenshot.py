# Copyright (C) 2026
# SPDX-License-Identifier: GPL-3.0-or-later

"""Capture an interactive screenshot with niri's built-in screenshot UI."""

import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import time
from typing import Callable
from uuid import uuid4

from gi.repository import GLib


class NiriScreenshotError(Exception):
    pass


def is_niri_session() -> bool:
    desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    return "niri" in desktops and shutil.which("niri") is not None


def _next_event(process: subprocess.Popen, pending: bytearray, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        newline = pending.find(b"\n")
        if newline >= 0:
            line = bytes(pending[:newline])
            del pending[:newline + 1]
            try:
                return json.loads(line)
            except json.JSONDecodeError as error:
                raise NiriScreenshotError("Invalid niri event stream response") from error

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise NiriScreenshotError("Timed out waiting for niri's screenshot UI")

        readable, _, _ = select.select([process.stdout], [], [], remaining)
        if not readable:
            raise NiriScreenshotError("Timed out waiting for niri's screenshot UI")

        chunk = os.read(process.stdout.fileno(), 65536)
        if not chunk:
            raise NiriScreenshotError("Niri's event stream closed unexpectedly")
        pending.extend(chunk)


def capture_niri_screenshot(
    delay_ms: int = 0,
    timeout: float = 120,
    screenshot_dir: Path | None = None,
    on_ui_opened: Callable[[], None] | None = None,
) -> str:
    if screenshot_dir is None:
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        screenshot_dir = (Path(pictures) if pictures else Path.home() / "Pictures") / "Screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    output_path = screenshot_dir / f"Gradia {time.strftime('%Y-%m-%d %H-%M-%S')}-{uuid4().hex}.png"

    try:
        stream = subprocess.Popen(
            ["niri", "msg", "--json", "event-stream"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise NiriScreenshotError(f"Could not start niri: {error}") from error

    pending = bytearray()
    try:
        # Niri sends the current state immediately after subscribing. Read one
        # event before opening the UI so a fast capture cannot be missed.
        _next_event(stream, pending, 5)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000)

        try:
            action = subprocess.run(
                ["niri", "msg", "action", "screenshot", "--path", str(output_path)],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NiriScreenshotError(f"Could not open niri's screenshot UI: {error}") from error

        if action.returncode != 0:
            detail = action.stderr.strip() or action.stdout.strip()
            raise NiriScreenshotError(detail or "Niri rejected the screenshot request")

        if on_ui_opened:
            on_ui_opened()

        deadline = time.monotonic() + timeout
        while True:
            event = _next_event(stream, pending, max(0, deadline - time.monotonic()))
            captured = event.get("ScreenshotCaptured")
            if captured is None:
                continue

            path = captured.get("path")
            if path is None:
                raise NiriScreenshotError(
                    "Screenshot was copied to the clipboard. Press Enter to save and open it in Gradia."
                )
            if path == str(output_path):
                if not output_path.is_file() or output_path.stat().st_size == 0:
                    raise NiriScreenshotError("Niri did not write the screenshot file")
                return path
    finally:
        stream.terminate()
        try:
            stream.wait(timeout=1)
        except subprocess.TimeoutExpired:
            stream.kill()
            stream.wait()
        stream.stdout.close()
