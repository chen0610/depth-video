from __future__ import annotations

import logging
import multiprocessing
import os
import platform
import sys
import traceback
from pathlib import Path

APP_TITLE = "Depth Anything V2 深度视频转换器"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 960
MIN_WINDOW_SIZE = (940, 700)


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


def main() -> None:
    logger = configure_logging()
    demo = None
    try:
        import webview

        from app import build_interface, launch_interface

        logger.info("Desktop dependencies imported")
        demo = build_interface()
        logger.info("Gradio interface built")
        _, local_url, _ = launch_interface(
            demo,
            server_name="127.0.0.1",
            server_port=None,
            prevent_thread_lock=True,
            quiet=True,
        )
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
