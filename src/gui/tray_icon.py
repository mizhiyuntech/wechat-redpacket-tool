"""系统托盘图标"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal
import os


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标"""

    toggle_signal = pyqtSignal()
    show_signal = pyqtSignal()
    quit_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置图标
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icon.ico")
        icon_path = os.path.abspath(icon_path)
        if os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
        else:
            self.setIcon(QApplication.style().standardIcon(
                QApplication.style().SP_ComputerIcon
            ))

        self.setToolTip("微信自动抢红包工具")
        self._setup_menu()
        self.activated.connect(self._on_activated)

    def _setup_menu(self):
        menu = QMenu()

        self._show_action = QAction("显示主窗口", menu)
        self._show_action.triggered.connect(self.show_signal.emit)
        menu.addAction(self._show_action)

        menu.addSeparator()

        self._toggle_action = QAction("开启抢包", menu)
        self._toggle_action.triggered.connect(self.toggle_signal.emit)
        menu.addAction(self._toggle_action)

        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit_signal.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_signal.emit()

    def update_status(self, running: bool):
        """更新托盘菜单状态"""
        if running:
            self._toggle_action.setText("停止抢包")
            self.setToolTip("微信自动抢红包 - 运行中")
        else:
            self._toggle_action.setText("开启抢包")
            self.setToolTip("微信自动抢红包 - 已停止")
