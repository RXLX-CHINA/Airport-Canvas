# Airport Canvas v1.0 Windows x64

绿色版解压后双击 AirportCanvas.exe。安装版提供开始菜单入口，并注册 ACP 文件类型、文件图标与打开命令。若 Windows 已有其他默认应用，可在默认应用设置中选择 Airport Canvas。

Extract the portable ZIP and launch AirportCanvas.exe. The installer adds a Start Menu shortcut and registers the ACP file type, icon and open command. If Windows already has another default app, select Airport Canvas in Default apps.

## 构建 / Build

Build prerequisites / 构建依赖: Windows x64, Python 3.12 x64, Microsoft C++ Build Tools, Nuitka, Inno Setup 6.

    python -m pip install -r requirements.txt Nuitka
    python build_windows.py

Use --portable-only to skip Inno Setup, or --iscc to specify its compiler path. Build outputs are placed in release/. The end-user packages launch AirportCanvas.exe directly and bundle the runtime.

使用 --portable-only 只生成绿色版，或用 --iscc 指定 Inno Setup 编译器。构建产物位于 release/。发行包自带运行库，用户直接启动 AirportCanvas.exe。

ZSQD retains its editable objects and ships without its two bitmap layers. The custom runway font is included. Review bundled dependency notices and the Allerta Stencil OFL text before public distribution.

ZSQD 保留可编辑对象，已移除两层位图。保留自制跑道字体。公开发布前请补齐随包依赖许可材料和 Allerta Stencil 的 OFL 正文。
