# 微信自动抢红包工具

Windows PC端微信自动抢红包桌面工具，用于商业收款及授权场景。

## 功能

- 自动检测微信PC端红包消息并抢夺
- 可配置抢包延迟（模拟自然行为）
- 指定群聊监控
- 金额统计与记录
- 系统托盘后台运行
- 声音提醒
- 定时开关
- 多微信实例支持

## 免责声明

本工具仅供学习交流、商业收款及经授权的自动化场景使用。使用本工具可能违反微信用户协议，用户需自行承担风险。首次启动时需阅读并同意完整免责声明。

## 使用方法

### 直接运行

```bash
pip install -r requirements.txt
python src/main.py
```

### 编译DLL（可选，提升点击速度）

需要MinGW或MSVC：

```bash
cd src/native
build_dll.bat
```

### 打包为EXE

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

生成的可执行文件在 `dist/` 目录。

## 技术栈

- **GUI**: PyQt5
- **检测**: Windows UI Automation (`uiautomation`)
- **原生加速**: C DLL (`ctypes`)
- **打包**: PyInstaller

## 项目结构

```
src/
├── main.py              # 程序入口
├── core/
│   ├── config.py        # 配置管理
│   ├── monitor.py       # 微信窗口监控
│   ├── grabber.py       # 红包抢夺逻辑
│   ├── scheduler.py     # 定时调度
│   └── statistics.py    # 金额统计
├── gui/
│   ├── main_window.py       # 主窗口
│   ├── disclaimer_dialog.py # 免责声明
│   ├── settings_dialog.py   # 设置面板
│   ├── statistics_widget.py # 统计面板
│   ├── tray_icon.py         # 系统托盘
│   └── styles.py            # QSS样式
└── native/
    ├── fast_click.c     # C快速点击库
    └── build_dll.bat    # DLL编译脚本
```

## 系统要求

- Windows 10/11
- Python 3.8+
- 微信PC端
