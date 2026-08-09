from __future__ import annotations

import logging
import multiprocessing
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import ProxyHandler, build_opener

APP_TITLE = "Depth Anything V2 深度视频转换器"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 960
MIN_WINDOW_SIZE = (940, 700)
STARTUP_RECOVERY_TIMEOUT_SECONDS = 20.0


def desktop_log_path() -> Path:
    override = os.environ.get("DEPTH_VIDEO_HOME")
    if override:
        app_data_dir = Path(override).expanduser().resolve()
    elif platform.system() == "Windows":
        app_data_dir = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        ) / "Longway" / "Depth Video"
    elif platform.system() == "Darwin":
        app_data_dir = (
            Path.home()
            / "Library"
            / "Application Support"
            / "Longway"
            / "Depth Video"
        )
    else:
        app_data_dir = Path.home() / ".local" / "share" / "longway" / "depth-video"

    log_dir = app_data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "desktop.log"


def configure_logging() -> logging.Logger:
    log_path = desktop_log_path()
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
        force=True,
    )
    logger = logging.getLogger("depth_video.desktop")
    logger.info("Starting Depth Video desktop host")
    return logger


def show_fatal_error(message: str) -> None:
    if platform.system() == "Windows":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_TITLE, 0x10)
        return

    print(message, file=sys.stderr)


def wait_for_gradio_startup(local_url: str, timeout: float) -> None:
    startup_url = urljoin(local_url, "gradio_api/startup-events")
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    last_error = "no response"

    while time.monotonic() < deadline:
        try:
            with opener.open(startup_url, timeout=2.0) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"HTTP {response.status}"
        except (OSError, URLError) as exc:
            last_error = str(exc)
        time.sleep(0.25)

    raise RuntimeError(
        f"Gradio did not become ready within {timeout:.0f}s: {last_error}"
    )


def main() -> None:
    logger = configure_logging()
    demo = None
    try:
        import webview

        from app import build_interface, launch_interface

        logger.info("Desktop dependencies imported")
        demo = build_interface()
        logger.info("Gradio interface built")
        try:
            _, local_url, _ = launch_interface(
                demo,
                server_name="127.0.0.1",
                server_port=None,
                prevent_thread_lock=True,
                quiet=True,
            )
        except Exception as launch_error:
            local_url = getattr(demo, "local_url", None)
            if "startup-events" not in str(launch_error) or not local_url:
                raise
            logger.warning(
                "Initial Gradio readiness check failed; waiting for %s",
                local_url,
            )
            wait_for_gradio_startup(local_url, STARTUP_RECOVERY_TIMEOUT_SECONDS)
            logger.info("Gradio became ready after the initial readiness failure")
        logger.info("Local server ready at %s", local_url)

        webview.create_window(
            APP_TITLE,
            local_url,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=MIN_WINDOW_SIZE,
            text_select=True,
        )
        logger.info("Starting native webview")
        webview.start(debug=False)
        logger.info("Native window closed")
    except Exception:
        detail = traceback.format_exc()
        logger.exception("Desktop startup failed")
        show_fatal_error(f"应用启动失败。\n\n{detail}")
        raise
    finally:
        if demo is not None:
            demo.close()
            logger.info("Local server stopped")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
