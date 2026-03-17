"""主窗口"""
import logging
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QTabWidget, QFrame,
    QSystemTrayIcon, QApplication
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QMetaObject, Q_ARG

from gui.styles import MAIN_STYLE
from gui.settings_dialog import SettingsDialog
from gui.statistics_widget import StatisticsWidget
from gui.tray_icon import TrayIcon
from core.config import Config
from core.monitor import WeChatMonitor
from core.grabber import RedPacketGrabber
from core.statistics import Statistics
from core.scheduler import Scheduler

logger = logging.getLogger(__name__)

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


class LogHandler(logging.Handler):
    """线程安全的日志Handler，通过invokeMethod转发到GUI线程"""

    def __init__(self, text_edit):
        super().__init__()
        self._text_edit = text_edit

    def emit(self, record):
        msg = self.format(record)
        QMetaObject.invokeMethod(
            self._text_edit, "append",
            Qt.QueuedConnection,
            Q_ARG(str, msg),
        )


class MainWindow(QMainWindow):
    """主窗口"""

    # 信号: 从工作线程安全地通知GUI线程
    _grab_success_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信自动抢红包工具")
        self.setMinimumSize(700, 550)

        # 初始化核心组件
        self._config = Config()
        self._statistics = Statistics()
        self._scheduler = Scheduler(self._config)
        self._monitor = WeChatMonitor(self._config, on_redpacket_found=self._on_redpacket_found)
        self._grabber = RedPacketGrabber(
            self._config, self._statistics, on_grab_success=self._on_grab_success_from_thread
        )

        self._setup_ui()
        self._setup_tray()
        self._setup_log_handler()
        self._setup_timers()

        # 连接信号到GUI线程槽
        self._grab_success_signal.connect(self._handle_grab_success)

        self.setStyleSheet(MAIN_STYLE)
        logger.info("程序初始化完成")

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 顶部状态栏
        status_frame = QFrame()
        status_frame.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_frame)

        self._status_label = QLabel("已停止")
        self._status_label.setObjectName("statusLabel")
        status_layout.addWidget(self._status_label)

        status_layout.addStretch()

        self._wechat_status = QLabel("微信: 未检测")
        self._wechat_status.setStyleSheet("color: white; font-size: 13px;")
        status_layout.addWidget(self._wechat_status)

        layout.addWidget(status_frame)

        # 控制按钮区
        ctrl_layout = QHBoxLayout()

        self._toggle_btn = QPushButton("开启抢包")
        self._toggle_btn.setObjectName("toggleBtn")
        self._toggle_btn.setProperty("running", False)
        self._toggle_btn.clicked.connect(self._toggle)
        ctrl_layout.addWidget(self._toggle_btn)

        settings_btn = QPushButton("设置")
        settings_btn.clicked.connect(self._open_settings)
        ctrl_layout.addWidget(settings_btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # 标签页
        tabs = QTabWidget()

        # 日志页
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self._log_view = QTextEdit()
        self._log_view.setObjectName("logView")
        self._log_view.setReadOnly(True)
        log_layout.addWidget(self._log_view)

        clear_log_btn = QPushButton("清除日志")
        clear_log_btn.clicked.connect(self._log_view.clear)
        log_layout.addWidget(clear_log_btn, alignment=Qt.AlignRight)

        tabs.addTab(log_widget, "日志")

        # 收款列表页
        self._stats_widget = StatisticsWidget(self._statistics)
        tabs.addTab(self._stats_widget, "收款列表")

        layout.addWidget(tabs)

    def _setup_tray(self):
        self._tray = TrayIcon(self)
        self._tray.show_signal.connect(self._show_from_tray)
        self._tray.toggle_signal.connect(self._toggle)
        self._tray.quit_signal.connect(self._quit)
        self._tray.show()

    def _setup_log_handler(self):
        handler = LogHandler(self._log_view)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

    def _setup_timers(self):
        # 定时检查调度
        self._schedule_timer = QTimer()
        self._schedule_timer.timeout.connect(self._check_schedule)
        self._schedule_timer.start(30000)  # 30秒检查一次

        # 定时刷新统计
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._stats_widget.refresh)
        self._stats_timer.start(5000)

        # 定时刷新微信状态
        self._wechat_status_timer = QTimer()
        self._wechat_status_timer.timeout.connect(self._refresh_wechat_status)
        self._wechat_status_timer.start(1000)

        self._refresh_wechat_status()

    def _toggle(self):
        """开关抢包功能"""
        if self._monitor.is_running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._config.set("enabled", True)
        self._config.save()
        self._monitor.start()
        self._update_ui_state(True)
        self._refresh_wechat_status()
        logger.info("抢包功能已开启")
        self._tray.showMessage("微信抢红包", "自动抢包已开启", QSystemTrayIcon.Information, 2000)

    def _stop(self):
        self._config.set("enabled", False)
        self._config.save()
        self._monitor.stop()
        self._update_ui_state(False)
        self._refresh_wechat_status()
        logger.info("抢包功能已停止")

    def _update_ui_state(self, running: bool):
        self._toggle_btn.setText("停止抢包" if running else "开启抢包")
        self._toggle_btn.setProperty("running", running)
        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)
        self._status_label.setText("运行中" if running else "已停止")
        self._tray.update_status(running)

    def _refresh_wechat_status(self):
        count = self._monitor.window_count
        if count > 0:
            self._wechat_status.setText(f"微信: 已检测 ({count})")
            self._wechat_status.setStyleSheet("color: #2ecc71; font-size: 13px;")
        elif self._monitor.is_running:
            self._wechat_status.setText("微信: 未找到")
            self._wechat_status.setStyleSheet("color: #f39c12; font-size: 13px;")
        else:
            self._wechat_status.setText("微信: 未检测")
            self._wechat_status.setStyleSheet("color: white; font-size: 13px;")

    def _on_redpacket_found(self, info):
        """检测到红包回调 (从工作线程调用，logger已线程安全)"""
        event_type = info.get("event_type", "redpacket")
        logger.info("检测到%s: %s", "转账" if event_type == "transfer" else "红包", info.get("text", ""))
        self._grabber.grab(info)

    def _on_grab_success_from_thread(self, record):
        """抢包成功回调 (从工作线程调用，通过信号转发到GUI线程)"""
        self._grab_success_signal.emit(record)

    def _handle_grab_success(self, record):
        """在GUI线程中处理抢包成功 (由信号触发)"""
        record_type = record.get("type", "红包")
        logger.info(
            "%s成功! 金额: %.2f元 | 来源: %s | 付款人: %s",
            record_type, record.get("amount", 0), record.get("source", ""), record.get("payer", "")
        )
        self._play_sound()
        self._stats_widget.refresh()
        QApplication.processEvents()
        self._tray.showMessage(
            f"{record_type}成功!",
            f"金额: {record.get('amount', 0):.2f}元\n"
            f"付款人: {record.get('payer', '未知')}\n"
            f"来源: {record.get('source', '')}",
            QSystemTrayIcon.Information, 3000
        )

    def _play_sound(self):
        """播放提示音 (使用Windows原生winsound)"""
        if not self._config.get("sound_enabled", True):
            return
        sound_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "grab_sound.wav")
        sound_path = os.path.abspath(sound_path)
        if os.path.exists(sound_path) and HAS_WINSOUND:
            try:
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                logger.debug("播放提示音失败: %s", e)
        elif HAS_WINSOUND:
            # 无自定义音频文件时播放系统提示音
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass

    def _check_schedule(self):
        """检查定时调度"""
        if not self._config.get("schedule_enabled"):
            return
        should_run = self._scheduler.should_run()
        if should_run and not self._monitor.is_running:
            logger.info("定时调度: 自动开启")
            self._start()
        elif not should_run and self._monitor.is_running:
            logger.info("定时调度: 自动关闭")
            self._stop()

    def _open_settings(self):
        dlg = SettingsDialog(self._config, self)
        dlg.exec_()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()

    def _quit(self):
        self._monitor.stop()
        QApplication.quit()

    def closeEvent(self, event):
        if self._config.get("minimize_to_tray", True):
            event.ignore()
            self.hide()
            self._tray.showMessage("微信抢红包", "程序已最小化到托盘", QSystemTrayIcon.Information, 2000)
        else:
            self._monitor.stop()
            event.accept()
