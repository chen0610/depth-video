#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "macOS desktop builds must run on macOS." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  "$PYTHON_BIN" -m pip install -r requirements-desktop.txt
fi

"$PYTHON_BIN" tools/make_icon.py --output-dir assets
iconutil -c icns assets/DepthVideo.iconset -o assets/icon.icns

MODEL_DESTINATION="$PROJECT_DIR/.build_assets/models/small"
if [[ "${WITHOUT_BUNDLED_SMALL_MODEL:-0}" == "1" ]]; then
  rm -rf "$MODEL_DESTINATION"
else
  "$PYTHON_BIN" tools/prepare_bundled_model.py \
    --cache-dir "$PROJECT_DIR/.cache/huggingface/hub" \
    --destination "$MODEL_DESTINATION"
fi

"$PYTHON_BIN" -m PyInstaller --noconfirm --clean depth_video.spec

APP_PATH="$PROJECT_DIR/dist/Depth Video.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Build completed without the expected app: $APP_PATH" >&2
  exit 1
fi

if [[ -n "${CODESIGN_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime --sign "$CODESIGN_IDENTITY" "$APP_PATH"
fi

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$PROJECT_DIR/dist/DepthVideo-macOS.zip"
echo "Desktop application: $APP_PATH"
