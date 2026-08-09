from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_ID = "depth-anything/Depth-Anything-V2-Small-hf"
REQUIRED_FILES = ("config.json", "preprocessor_config.json", "model.safetensors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a self-contained Small model")
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    cache_dir = args.cache_dir.resolve()
    destination = args.destination.resolve()
    snapshot_path = Path(
        snapshot_download(
            repo_id=MODEL_ID,
            cache_dir=cache_dir,
            local_files_only=args.offline,
        )
    )

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(snapshot_path, destination, symlinks=False)

    missing = [name for name in REQUIRED_FILES if not (destination / name).is_file()]
    if missing:
        raise RuntimeError(f"Bundled model is incomplete: {', '.join(missing)}")

    total_bytes = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    print(f"Prepared {MODEL_ID} at {destination} ({total_bytes / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
