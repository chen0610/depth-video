from __future__ import annotations

import argparse
import gc
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generator

# Some model operations are not implemented by every MPS release. PyTorch can
# transparently run those individual operations on the CPU when this is set
# before torch is imported.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
IS_FROZEN = bool(getattr(sys, "frozen", False))


def default_app_data_dir() -> Path:
    override = os.environ.get("DEPTH_VIDEO_HOME")
    if override:
        return Path(override).expanduser().resolve()

    if not IS_FROZEN:
        return SOURCE_DIR / ".cache"

    system = platform.system()
    if system == "Windows":
        base_dir = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        return base_dir / "Longway" / "Depth Video"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Longway" / "Depth Video"

    base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base_dir / "longway" / "depth-video"


APP_DATA_DIR = default_app_data_dir()
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(APP_DATA_DIR / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import gradio as gr
import imageio_ffmpeg
import numpy as np
import torch
import torch.nn.functional as functional
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation


APP_TITLE = "Depth Anything V2 深度视频转换器"
SUPPORTED_EXTENSIONS = {".mp4", ".mov"}
MODEL_IDS = {
    "Small": "depth-anything/Depth-Anything-V2-Small-hf",
    "Base": "depth-anything/Depth-Anything-V2-Base-hf",
    "Large": "depth-anything/Depth-Anything-V2-Large-hf",
}
RESOLUTION_HEIGHTS = {
    "原始分辨率": None,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
}
OUTPUT_DIR = Path(tempfile.gettempdir()) / "depth_video_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UI_CSS_PATH = RESOURCE_DIR / "ui.css"
UI_JS = (RESOURCE_DIR / "ui.js").read_text(encoding="utf-8")
BUNDLED_SMALL_MODEL_DIR = RESOURCE_DIR / "models" / "small"


def build_ui_head() -> str:
    vendor_dir = RESOURCE_DIR / "vendor"
    script_paths = [vendor_dir / "gsap.min.js", vendor_dir / "ScrollTrigger.min.js"]
    if all(path.is_file() for path in script_paths):
        scripts = "\n".join(path.read_text(encoding="utf-8") for path in script_paths)
        return f"<script>{scripts}</script>"

    return """
    <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/ScrollTrigger.min.js"></script>
    """


UI_HEAD = build_ui_head()
UI_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.lime,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.gray,
    radius_size=gr.themes.sizes.radius_sm,
    font=("Geist", "Segoe UI Variable", "Segoe UI", "system-ui", "sans-serif"),
    font_mono=("Geist Mono", "Cascadia Code", "Consolas", "monospace"),
)

_MODEL_LOCK = threading.RLock()
_MODEL_BUNDLE: "ModelBundle | None" = None


@dataclass(frozen=True)
class DeviceInfo:
    device: torch.device
    label: str


@dataclass
class ModelBundle:
    name: str
    device_info: DeviceInfo
    processor: Any
    model: torch.nn.Module


def select_device() -> DeviceInfo:
    """Choose the best accelerator supported by the current PyTorch build."""
    system = platform.system()

    if system == "Windows" and torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        return DeviceInfo(torch.device("cuda"), f"CUDA - {gpu_name}")

    mps_backend = getattr(torch.backends, "mps", None)
    if system == "Darwin" and mps_backend and mps_backend.is_available():
        return DeviceInfo(torch.device("mps"), "Apple Silicon MPS")

    # These branches make the script usable on other operating systems without
    # changing the Windows/macOS selection order required by the application.
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        return DeviceInfo(torch.device("cuda"), f"CUDA - {gpu_name}")
    if mps_backend and mps_backend.is_available():
        return DeviceInfo(torch.device("mps"), "Apple MPS")

    return DeviceInfo(torch.device("cpu"), "CPU")


def release_accelerator_cache() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    mps_module = getattr(torch, "mps", None)
    if mps_module is not None and hasattr(mps_module, "empty_cache"):
        try:
            mps_module.empty_cache()
        except RuntimeError:
            pass


def load_model(model_name: str, device_info: DeviceInfo) -> ModelBundle:
    """Keep only one model resident so switching sizes does not exhaust VRAM."""
    global _MODEL_BUNDLE

    if model_name not in MODEL_IDS:
        raise ValueError(f"不支持的模型: {model_name}")

    with _MODEL_LOCK:
        if (
            _MODEL_BUNDLE is not None
            and _MODEL_BUNDLE.name == model_name
            and _MODEL_BUNDLE.device_info.device == device_info.device
        ):
            return _MODEL_BUNDLE

        old_bundle = _MODEL_BUNDLE
        _MODEL_BUNDLE = None
        if old_bundle is not None:
            del old_bundle
            gc.collect()
            release_accelerator_cache()

        model_source: str | Path = MODEL_IDS[model_name]
        if model_name == "Small" and (BUNDLED_SMALL_MODEL_DIR / "config.json").is_file():
            model_source = BUNDLED_SMALL_MODEL_DIR

        processor = AutoImageProcessor.from_pretrained(model_source)
        model = AutoModelForDepthEstimation.from_pretrained(model_source)
        model.eval()
        model.to(device_info.device)

        _MODEL_BUNDLE = ModelBundle(
            name=model_name,
            device_info=device_info,
            processor=processor,
            model=model,
        )
        return _MODEL_BUNDLE


def even_dimension(value: float) -> int:
    return max(2, int(round(value / 2.0) * 2))


def calculate_output_size(
    source_size: tuple[int, int], resolution_name: str
) -> tuple[int, int]:
    """Scale the shorter edge to the selected preset and preserve aspect ratio."""
    width, height = source_size
    if width <= 0 or height <= 0:
        raise ValueError("视频分辨率无效")

    target_short_edge = RESOLUTION_HEIGHTS.get(resolution_name)
    if resolution_name not in RESOLUTION_HEIGHTS:
        raise ValueError(f"不支持的输出分辨率: {resolution_name}")

    if target_short_edge is None:
        return even_dimension(width), even_dimension(height)

    scale = target_short_edge / min(width, height)
    return even_dimension(width * scale), even_dimension(height * scale)


def estimate_total_frames(metadata: dict[str, Any], fps: float) -> int | None:
    frame_count = metadata.get("nframes")
    if isinstance(frame_count, (int, float)) and np.isfinite(frame_count):
        if frame_count > 0:
            return int(round(frame_count))

    duration = metadata.get("duration")
    if isinstance(duration, (int, float)) and np.isfinite(duration):
        if duration > 0:
            return max(1, int(round(duration * fps)))
    return None


def infer_depth(image: Image.Image, bundle: ModelBundle) -> np.ndarray:
    inputs = bundle.processor(images=image, return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(bundle.device_info.device)

    autocast_context = (
        torch.autocast(device_type="cuda", dtype=torch.float16)
        if bundle.device_info.device.type == "cuda"
        else nullcontext()
    )
    with torch.inference_mode(), autocast_context:
        prediction = bundle.model(pixel_values=pixel_values).predicted_depth
        prediction = functional.interpolate(
            prediction.unsqueeze(1),
            size=(image.height, image.width),
            mode="bicubic",
            align_corners=False,
        )[0, 0]

    return prediction.float().cpu().numpy()


class TemporalDepthFilter:
    """Stabilize relative-depth range and per-pixel intensity over time."""

    def __init__(self, strength: float) -> None:
        self.strength = float(np.clip(strength, 0.0, 0.95))
        self.previous_frame: np.ndarray | None = None
        self.low: float | None = None
        self.high: float | None = None

    def apply(self, depth: np.ndarray) -> np.ndarray:
        finite = depth[np.isfinite(depth)]
        if finite.size == 0:
            raise RuntimeError("模型输出了无效深度数据")

        current_low, current_high = np.percentile(finite, (2.0, 98.0))
        current_low = float(current_low)
        current_high = float(current_high)
        if current_high - current_low < 1e-6:
            current_low = float(finite.min())
            current_high = float(finite.max())
        if current_high - current_low < 1e-6:
            return np.zeros_like(depth, dtype=np.float32)

        current_normalized = np.clip(
            (depth - current_low) / max(current_high - current_low, 1e-6),
            0.0,
            1.0,
        ).astype(np.float32)

        # A large frame-wide change is usually a cut. Resetting avoids carrying
        # the previous shot into the new one as a visible gray afterimage.
        is_scene_cut = False
        if self.previous_frame is not None:
            mean_change = float(np.mean(np.abs(current_normalized - self.previous_frame)))
            is_scene_cut = mean_change > 0.35

        if (
            self.low is None
            or self.high is None
            or self.strength == 0.0
            or is_scene_cut
        ):
            stable_low, stable_high = current_low, current_high
            normalized = current_normalized
        else:
            stable_low = self.strength * self.low + (1.0 - self.strength) * current_low
            stable_high = self.strength * self.high + (1.0 - self.strength) * current_high
            normalized = np.clip(
                (depth - stable_low) / max(stable_high - stable_low, 1e-6),
                0.0,
                1.0,
            ).astype(np.float32)

        if self.previous_frame is not None and self.strength > 0.0 and not is_scene_cut:
            normalized = (
                self.strength * self.previous_frame
                + (1.0 - self.strength) * normalized
            ).astype(np.float32)

        self.previous_frame = normalized
        self.low = stable_low
        self.high = stable_high
        return normalized


def read_video_frames(
    video_path: Path,
) -> tuple[dict[str, Any], Generator[bytes, None, None]]:
    reader = imageio_ffmpeg.read_frames(str(video_path), pix_fmt="rgb24")
    try:
        metadata = next(reader)
    except StopIteration as exc:
        reader.close()
        raise RuntimeError("无法读取视频元数据") from exc
    return metadata, reader


def open_video_writer(
    output_path: Path, size: tuple[int, int], fps: float
) -> Generator[Any, Any, None]:
    writer = imageio_ffmpeg.write_frames(
        str(output_path),
        size,
        fps=fps,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        quality=7,
        macro_block_size=2,
        output_params=["-preset", "medium", "-movflags", "+faststart"],
    )
    writer.send(None)
    return writer


def mux_original_audio(silent_video: Path, source_video: Path, output_path: Path) -> None:
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(silent_video),
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip()[-1500:]
        raise RuntimeError(f"音频复用失败: {detail or 'ffmpeg 未返回详细信息'}")


def normalized_input_path(video: Any) -> Path:
    raw_path = getattr(video, "name", video)
    if not raw_path:
        raise ValueError("请先上传 MP4 或 MOV 视频")
    path = Path(str(raw_path)).expanduser().resolve()
    if not path.is_file():
        raise ValueError("上传的视频文件不存在")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("仅支持 MP4 和 MOV 输入")
    return path


def safe_output_stem(source: Path) -> str:
    stem = re.sub(r"[^\w.-]+", "_", source.stem, flags=re.UNICODE).strip("._")
    return (stem or "video")[:80]


def convert_video(
    input_video: Any,
    model_name: str,
    resolution_name: str,
    invert: bool,
    smoothing: float,
    keep_audio: bool,
    progress: gr.Progress = gr.Progress(),
) -> tuple[str, str]:
    source_path = normalized_input_path(input_video)
    device_info = select_device()
    progress(0.0, desc=f"加载 {model_name} 模型")

    try:
        bundle = load_model(model_name, device_info)
    except Exception as exc:
        raise gr.Error(f"模型加载失败: {exc}") from exc

    unique_id = uuid.uuid4().hex[:10]
    output_name = f"{safe_output_stem(source_path)}_depth_{model_name.lower()}_{unique_id}.mp4"
    final_path = OUTPUT_DIR / output_name

    try:
        with tempfile.TemporaryDirectory(prefix="depth_video_work_") as work_dir:
            silent_path = Path(work_dir) / "depth_silent.mp4"
            metadata, reader = read_video_frames(source_path)

            source_size_value = metadata.get("size") or metadata.get("source_size")
            if not source_size_value or len(source_size_value) != 2:
                reader.close()
                raise RuntimeError("无法确定视频分辨率")
            source_size = (int(source_size_value[0]), int(source_size_value[1]))
            output_size = calculate_output_size(source_size, resolution_name)

            fps = float(metadata.get("fps") or 30.0)
            if not np.isfinite(fps) or fps <= 0.0 or fps > 240.0:
                fps = 30.0
            total_frames = estimate_total_frames(metadata, fps)
            update_every = max(1, (total_frames or 100) // 100)

            writer = open_video_writer(silent_path, output_size, fps)
            temporal_filter = TemporalDepthFilter(float(smoothing))
            processed_frames = 0
            try:
                for frame_bytes in reader:
                    frame = np.frombuffer(frame_bytes, dtype=np.uint8)
                    expected_values = source_size[0] * source_size[1] * 3
                    if frame.size != expected_values:
                        raise RuntimeError(
                            f"视频帧大小异常: 期望 {expected_values} 字节值，"
                            f"实际 {frame.size} 字节值"
                        )
                    frame = frame.reshape((source_size[1], source_size[0], 3))
                    image = Image.fromarray(frame, mode="RGB")
                    if image.size != output_size:
                        image = image.resize(output_size, Image.Resampling.LANCZOS)

                    depth = infer_depth(image, bundle)
                    normalized = temporal_filter.apply(depth)
                    if invert:
                        normalized = 1.0 - normalized
                    gray = np.rint(normalized * 255.0).astype(np.uint8)
                    rgb_gray = np.repeat(gray[:, :, None], 3, axis=2)
                    writer.send(rgb_gray.tobytes())

                    processed_frames += 1
                    if processed_frames % update_every == 0:
                        if total_frames:
                            progress(
                                (min(processed_frames, total_frames), total_frames),
                                desc=f"处理第 {processed_frames} 帧",
                            )
                        else:
                            progress(0.5, desc=f"已处理 {processed_frames} 帧")
            finally:
                reader.close()
                writer.close()

            if processed_frames == 0:
                raise RuntimeError("视频中没有可读取的帧")

            progress(0.97, desc="封装 MP4")
            if keep_audio:
                mux_original_audio(silent_path, source_path, final_path)
            else:
                silent_path.replace(final_path)

        progress(1.0, desc="完成")
        status = (
            f"完成 | {processed_frames} 帧 | {output_size[0]}x{output_size[1]} "
            f"| {fps:.3f} FPS | {device_info.label}"
        )
        return str(final_path), status
    except gr.Error:
        if final_path.exists():
            final_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        if final_path.exists():
            final_path.unlink(missing_ok=True)
        release_accelerator_cache()
        message = str(exc).strip() or exc.__class__.__name__
        if "out of memory" in message.lower():
            message += "；请改用更小模型或更低输出分辨率"
        raise gr.Error(f"转换失败: {message}") from exc


def build_interface() -> gr.Blocks:
    device_info = select_device()
    device_kind = device_info.device.type.upper()
    with gr.Blocks(title=APP_TITLE, fill_width=True) as demo:
        with gr.Column(elem_id="studio-shell"):
            gr.HTML(
                f"""
                <header class="studio-nav">
                    <div class="studio-brand">
                        <span class="brand-glyph" aria-hidden="true">
                            <i></i><i></i><i></i><i></i>
                        </span>
                        <span class="brand-name">Depth Video</span>
                    </div>
                    <div class="device-status" title="{device_info.label}">
                        <span class="status-dot" aria-hidden="true"></span>
                        <span class="device-kind">{device_kind}</span>
                        <span class="device-name">{device_info.label}</span>
                    </div>
                </header>
                """,
                elem_classes="studio-chrome",
            )

            with gr.Column(elem_classes="studio-content"):
                gr.HTML(
                    """
                    <div class="studio-titlebar">
                        <h1>
                            Depth
                            <span class="depth-strip" aria-hidden="true">
                                <i></i><i></i><i></i><i></i><i></i>
                            </span>
                            Video <sup>V2</sup>
                        </h1>
                    </div>
                    """,
                    elem_classes="title-block",
                )

                with gr.Row(equal_height=True, elem_classes="media-grid"):
                    with gr.Column(scale=1, min_width=320, elem_classes="media-cell"):
                        gr.HTML(
                            '<div class="media-heading"><span>原始画面</span><b>INPUT</b></div>'
                        )
                        input_video = gr.Video(
                            label="输入视频",
                            show_label=False,
                            sources=["upload"],
                            format=None,
                            elem_classes=["media-panel", "source-media"],
                        )

                    with gr.Column(scale=1, min_width=320, elem_classes="media-cell"):
                        gr.HTML(
                            '<div class="media-heading"><span>深度结果</span><b>OUTPUT</b></div>'
                        )
                        output_video = gr.Video(
                            label="深度视频",
                            show_label=False,
                            format="mp4",
                            elem_classes=["media-panel", "depth-media"],
                        )

                with gr.Column(elem_classes="control-surface"):
                    with gr.Row(elem_classes="control-grid"):
                        model_name = gr.Dropdown(
                            choices=[
                                ("Small · Apache 2.0", "Small"),
                                ("Base · Non-commercial", "Base"),
                                ("Large · Non-commercial", "Large"),
                            ],
                            value="Small",
                            label="模型",
                            scale=3,
                            min_width=180,
                            elem_classes="control-field",
                        )
                        resolution_name = gr.Dropdown(
                            choices=list(RESOLUTION_HEIGHTS),
                            value="原始分辨率",
                            label="输出尺寸",
                            scale=3,
                            min_width=180,
                            elem_classes="control-field",
                        )
                        smoothing = gr.Slider(
                            minimum=0.0,
                            maximum=0.95,
                            value=0.65,
                            step=0.05,
                            label="时间稳定性",
                            scale=6,
                            min_width=280,
                            elem_classes=["control-field", "smoothing-control"],
                        )

                    with gr.Accordion(
                        "输出选项",
                        open=True,
                        elem_classes="output-accordion",
                    ):
                        with gr.Row(elem_classes="option-row"):
                            invert = gr.Checkbox(
                                value=False,
                                label="黑白反转",
                                scale=1,
                                elem_classes="option-toggle",
                            )
                            keep_audio = gr.Checkbox(
                                value=True,
                                label="保留原始音频",
                                scale=1,
                                elem_classes="option-toggle",
                            )

                with gr.Row(elem_classes="action-bar"):
                    status = gr.Textbox(
                        value=f"READY  /  {device_info.label}",
                        label="运行状态",
                        show_label=False,
                        container=False,
                        interactive=False,
                        scale=8,
                        elem_id="run-status",
                    )
                    convert_button = gr.Button(
                        "开始转换",
                        variant="primary",
                        scale=4,
                        min_width=220,
                        elem_id="convert-action",
                    )

                gr.HTML(
                    """
                    <footer class="studio-footer">
                        <span>Developed by <strong>Longway</strong></span>
                        <a href="mailto:longway1021@gmail.com">longway1021@gmail.com</a>
                    </footer>
                    """,
                    elem_classes="ownership-block",
                )

        convert_button.click(
            fn=convert_video,
            inputs=[
                input_video,
                model_name,
                resolution_name,
                invert,
                smoothing,
                keep_audio,
            ],
            outputs=[output_video, status],
            concurrency_limit=1,
            api_name="convert",
        )
    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--host", default="127.0.0.1", help="Gradio 监听地址")
    parser.add_argument("--port", type=int, default=7860, help="Gradio 监听端口")
    parser.add_argument("--share", action="store_true", help="创建 Gradio 临时公网链接")
    parser.add_argument("--inbrowser", action="store_true", help="启动后打开浏览器")
    return parser.parse_args()


def launch_interface(
    demo: gr.Blocks,
    *,
    server_name: str = "127.0.0.1",
    server_port: int | None = 7860,
    share: bool = False,
    inbrowser: bool = False,
    prevent_thread_lock: bool = False,
    quiet: bool = False,
) -> tuple[Any, str, str]:
    favicon_path = RESOURCE_DIR / "assets" / "icon.png"
    return demo.queue(default_concurrency_limit=1).launch(
        server_name=server_name,
        server_port=server_port,
        share=share,
        inbrowser=inbrowser,
        prevent_thread_lock=prevent_thread_lock,
        quiet=quiet,
        allowed_paths=[str(OUTPUT_DIR)],
        footer_links=[],
        theme=UI_THEME,
        css_paths=UI_CSS_PATH,
        js=UI_JS,
        head=UI_HEAD,
        favicon_path=favicon_path if favicon_path.is_file() else None,
        ssr_mode=False,
    )


def main() -> None:
    args = parse_args()
    demo = build_interface()
    launch_interface(
        demo,
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        inbrowser=args.inbrowser,
    )


if __name__ == "__main__":
    main()
