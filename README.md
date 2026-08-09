# Depth Anything V2 深度视频转换器

[![Latest Release](https://img.shields.io/github/v/release/chen0610/depth-video?display_name=tag&sort=semver)](https://github.com/chen0610/depth-video/releases/latest)
[![Windows](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4)](https://github.com/chen0610/depth-video/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB)](https://www.python.org/)

一个本地运行的 Depth Anything V2 深度视频转换器。应用逐帧生成灰度相对深度视频，支持 MP4 / MOV、CUDA / MPS 自动加速、时间平滑、音频保留和 H.264 MP4 导出。

[下载最新桌面版](https://github.com/chen0610/depth-video/releases/latest) · [查看源码安装](#源码运行环境) · [联系开发者](mailto:longway1021@gmail.com)

![Depth Video 桌面界面：原始视频与灰度深度结果对照](docs/images/depth-video-preview.png)

## 功能

- Depth Anything V2 Small / Base / Large 模型选择
- Windows NVIDIA CUDA、macOS Apple Silicon MPS 自动选择，不可用时回退到 CPU
- 原始分辨率、480p、720p、1080p 输出，保持画面比例
- 黑白反转
- 基于稳定分位范围和逐像素 EMA 的时间平滑
- 自动检测镜头切换，减少平滑导致的跨镜头残影
- 可选保留原始音频，转码为 AAC
- `imageio-ffmpeg` 随 Python wheel 提供 ffmpeg，普通安装无需单独配置 ffmpeg

## 下载桌面版

### Windows 10 / 11 x64

前往 [最新 Release](https://github.com/chen0610/depth-video/releases/latest)，下载：

- [`DepthVideo-Windows-x64-CPU.zip`](https://github.com/chen0610/depth-video/releases/latest/download/DepthVideo-Windows-x64-CPU.zip)
- [`DepthVideo-v1.0.0-SHA256SUMS.txt`](https://github.com/chen0610/depth-video/releases/latest/download/DepthVideo-v1.0.0-SHA256SUMS.txt)（可选校验）

解压 ZIP，进入 `DepthVideo` 目录并双击 `DepthVideo.exe`。便携包已包含 Python、CPU 版 PyTorch、Gradio、ffmpeg、WebView 宿主和 Small 模型，不需要配置 Python 环境。

为控制下载体积，官方便携包不内置 NVIDIA CUDA 运行库，只使用 CPU。需要 GPU 加速时，请按 [Windows NVIDIA CUDA](#windows-nvidia-cuda) 从源码运行，或自行构建 CUDA 桌面包。

当前 Windows 版本未进行代码签名，SmartScreen 可能显示“Windows 已保护你的电脑”。请先确认文件来自本仓库的 Release，并将以下命令的结果与 `DepthVideo-v1.0.0-SHA256SUMS.txt` 对照，再决定是否运行：

```powershell
Get-FileHash .\DepthVideo-Windows-x64-CPU.zip -Algorithm SHA256
```

默认构建内置 Small 权重，可离线开始转换。Base 和 Large 权重不内置，首次选择时仍需联网下载。

### macOS

当前 Release 暂未提供预编译的 macOS `.app`。macOS 用户可按下方命令从源码运行，或在自己的 Mac 上执行 `build_macos.sh` 构建。公开分发的 macOS 应用仍需要开发者证书签名和 Apple notarization，不能在 Windows 上可靠生成。

桌面版的模型与日志保存在用户数据目录：

- Windows：`%LOCALAPPDATA%\Longway\Depth Video`
- macOS：`~/Library/Application Support/Longway/Depth Video`

Windows 10/11 通常已安装 Microsoft Edge WebView2 Runtime。若精简系统移除了该组件，需要从微软官方安装 WebView2 Runtime；这不是 Python 环境依赖。

## 构建桌面版

PyInstaller 不是跨平台编译器。Windows 应用必须在 Windows 构建，macOS `.app` 必须在 macOS 构建。

`dist/` 是开发者本地构建目录，已通过 `.gitignore` 排除，不会出现在克隆后的仓库中。面向用户的可下载二进制统一发布在 [GitHub Releases](https://github.com/chen0610/depth-video/releases)。

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\build_windows.ps1 -Zip
```

默认安装 CPU 版 PyTorch、生成图标、准备 Small 模型，并输出 `dist\CPU\DepthVideo\DepthVideo.exe` 和 `dist\DepthVideo-Windows-x64-CPU.zip`。CPU / CUDA 变体使用隔离目录，不会互相覆盖；`dist/` 仍只存在于构建机本地。

自行构建 CUDA 12.6 桌面包：

```powershell
.\build_windows.ps1 -TorchVariant cu126 -Zip
```

CUDA 13.0 使用 `-TorchVariant cu130`。已有依赖时可使用 `-SkipInstall`，但该选项不会检查或替换当前 PyTorch 变体；不内置 Small 模型时使用 `-WithoutBundledSmallModel`。

macOS：

```bash
chmod +x build_macos.sh
./build_macos.sh
```

输出为 `dist/Depth Video.app` 和 `dist/DepthVideo-macOS.zip`。通过环境变量 `WITHOUT_BUNDLED_SMALL_MODEL=1` 可跳过内置模型；配置 `CODESIGN_IDENTITY` 后脚本会执行本地代码签名。面向其他用户公开分发时，Windows 和 macOS 产物都应使用开发者证书签名；macOS 还应完成 Apple notarization，当前脚本不代替证书申请和公证提交。

## 源码运行环境

- Python 3.10 - 3.12（推荐 Python 3.11）
- Windows 10/11，或 macOS 14+
- 首次选择模型时需联网下载 Hugging Face 权重，缓存位于项目的 `.cache/huggingface`
- 磁盘空间取决于模型：Small 约 100 MB，Base 约 400 MB，Large 约 1.4 GB

## Windows NVIDIA CUDA

官方 Windows 便携包是固定的 CPU 构建，不能通过单独安装 CUDA Toolkit 原地切换为 GPU。PyInstaller 已将 CPU 版 PyTorch 冻结进应用；GPU 模式必须使用包含 CUDA 的 PyTorch wheel 从源码运行，或按上一节自行打包。

1. 安装或更新 [NVIDIA 显卡驱动](https://www.nvidia.com/Download/index.aspx)，然后确认 PowerShell 能识别显卡：

```powershell
nvidia-smi
```

2. 在项目目录创建独立环境：

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

3. 安装 CUDA 版 PyTorch。项目当前验证过 CUDA 12.6 wheel：

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements.txt
```

也可在 [PyTorch 官方安装选择器](https://pytorch.org/get-started/locally/)中按当前驱动选择受支持的 CUDA wheel。若明确使用 CUDA 13.0：

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130
python -m pip install -r requirements.txt
```

4. 验证 GPU 并启动：

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python app.py --inbrowser
```

PyTorch wheel 已包含所需 CUDA 运行库，通常不需要单独安装完整 CUDA Toolkit；仍然必须有兼容的 NVIDIA 驱动。若验证结果是 `False`，不要继续打包 CUDA 版，先处理驱动或 wheel 不匹配问题。

## Windows CPU 源码安装

没有 NVIDIA GPU 时：

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python app.py --inbrowser
```

## macOS 安装

Apple Silicon 与 Intel Mac 使用同一套命令；Apple Silicon 在 MPS 可用时会自动启用 GPU，Intel Mac 回退到 CPU。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch torchvision
python -m pip install -r requirements.txt
python app.py --inbrowser
```

默认地址为 <http://127.0.0.1:7860>。若端口被占用：

```bash
python app.py --port 7861
```

## 加速状态检查

Windows CUDA：

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

macOS MPS：

```bash
python -c "import torch; print(torch.backends.mps.is_available())"
```

界面底部的“状态”会显示实际选中的设备。应用不自行安装 CUDA；是否能启用 CUDA 取决于 NVIDIA 驱动和当前虚拟环境中的 PyTorch wheel。完整 CUDA Toolkit 不是 PyTorch 预编译 wheel 的必要条件。

## 使用

1. 上传 `.mp4` 或 `.mov` 视频。
2. 选择模型、分辨率和时间平滑强度。
3. 根据需要开启黑白反转或关闭音频保留。
4. 点击“开始转换”，完成后在右侧预览或下载 MP4。

480p / 720p / 1080p 代表将输出的短边设为对应像素数，长边按原始比例计算。因此竖屏 1080p 视频通常为 1080x1920。

## 模型与许可

| 模型 | 参数量 | 权重许可 | 建议用途 |
| --- | ---: | --- | --- |
| Small | 24.8M | Apache-2.0 | 默认、商业用途、较小显存 |
| Base | 97.5M | CC-BY-NC-4.0 | 非商业、更高质量 |
| Large | 335.3M | CC-BY-NC-4.0 | 非商业、高显存设备 |

源代码的 Apache-2.0 许可不会改变 Base / Large 模型权重的非商业限制。用于商业场景时应选择 Small，并自行确认输入视频和输出内容的权利。

## 实现边界

- 输出是单目相对深度，不是米、毫米等真实距离。
- 默认是近处较亮、远处较暗；“黑白反转”可切换显示方向。
- 时间平滑越强，静态画面闪烁越少，但快速运动边缘可能产生短暂残影。
- 变帧率输入会按 ffmpeg 解析的平均帧率输出为恒定帧率。
- HDR 和特殊色彩管理信息不会保留；输出是 8-bit yuv420p。
- 同一时间只运行一个转换任务，以避免多任务竞争 GPU 显存。

## 复杂度

对于 `F` 帧、输出分辨率 `W x H` 的视频：

- 时间复杂度为 `O(F * (M + W*H))`，其中 `M` 是选定模型单帧推理代价。
- 视频帧使用流式读写，额外内存为 `O(W*H)`；总内存主要由模型权重、中间特征和两张深度帧占用。

## 开发者

本工具由 **Longway** 开发和维护。

联系邮箱：[longway1021@gmail.com](mailto:longway1021@gmail.com)

## 官方资料

- [Depth Anything V2 官方仓库](https://github.com/DepthAnything/Depth-Anything-V2)
- [Transformers: Depth Anything V2](https://huggingface.co/docs/transformers/model_doc/depth_anything_v2)
- [PyTorch 本地安装](https://pytorch.org/get-started/locally/)
- [PyTorch MPS 后端](https://docs.pytorch.org/docs/stable/notes/mps.html)
- [Gradio Video 组件](https://www.gradio.app/docs/gradio/video)
