"""设置面板"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QSpinBox, QCheckBox, QTimeEdit, QListWidget, QLineEdit,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTime


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("设置")
        self.setMinimumSize(480, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 抢包设置
        grab_group = QGroupBox("抢包设置")
        grab_layout = QFormLayout(grab_group)

        self._delay_min = QSpinBox()
        self._delay_min.setRange(0, 10000)
        self._delay_min.setSuffix(" 毫秒")
        grab_layout.addRow("最小延迟:", self._delay_min)

        self._delay_max = QSpinBox()
        self._delay_max.setRange(0, 10000)
        self._delay_max.setSuffix(" 毫秒")
        grab_layout.addRow("最大延迟:", self._delay_max)

        self._transfer_enabled = QCheckBox("启用普通转账监听/收款")
        grab_layout.addRow(self._transfer_enabled)

        self._transfer_delay = QSpinBox()
        self._transfer_delay.setRange(0, 30000)
        self._transfer_delay.setSuffix(" 毫秒")
        grab_layout.addRow("延迟收款时间:", self._transfer_delay)

        self._check_interval = QSpinBox()
        self._check_interval.setRange(100, 5000)
        self._check_interval.setSuffix(" 毫秒")
        grab_layout.addRow("检测间隔:", self._check_interval)

        self._sound_enabled = QCheckBox("抢到红包播放提示音")
        grab_layout.addRow(self._sound_enabled)

        layout.addWidget(grab_group)

        # 定时设置
        schedule_group = QGroupBox("定时开关")
        schedule_layout = QFormLayout(schedule_group)

        self._schedule_enabled = QCheckBox("启用定时功能")
        schedule_layout.addRow(self._schedule_enabled)

        self._schedule_start = QTimeEdit()
        self._schedule_start.setDisplayFormat("HH:mm")
        schedule_layout.addRow("开始时间:", self._schedule_start)

        self._schedule_end = QTimeEdit()
        self._schedule_end.setDisplayFormat("HH:mm")
        schedule_layout.addRow("结束时间:", self._schedule_end)

        layout.addWidget(schedule_group)

        # 监控群聊设置
        chat_group = QGroupBox("监控群聊")
        chat_layout = QVBoxLayout(chat_group)

        self._monitor_all = QCheckBox("监控所有群聊")
        self._monitor_all.toggled.connect(self._on_monitor_all_toggled)
        chat_layout.addWidget(self._monitor_all)

        self._chat_list = QListWidget()
        chat_layout.addWidget(self._chat_list)

        add_layout = QHBoxLayout()
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("输入群聊名称...")
        add_layout.addWidget(self._chat_input)

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_chat)
        add_layout.addWidget(add_btn)

        remove_btn = QPushButton("删除选中")
        remove_btn.setObjectName("dangerBtn")
        remove_btn.clicked.connect(self._remove_chat)
        add_layout.addWidget(remove_btn)

        chat_layout.addLayout(add_layout)
        layout.addWidget(chat_group)

        # 其他设置
        other_group = QGroupBox("其他")
        other_layout = QFormLayout(other_group)

        self._minimize_to_tray = QCheckBox("关闭时最小化到系统托盘")
        other_layout.addRow(self._minimize_to_tray)

        self._multi_instance = QCheckBox("支持多个微信实例")
        other_layout.addRow(self._multi_instance)

        layout.addWidget(other_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("dangerBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_config(self):
        self._delay_min.setValue(self._config.get("delay_min_ms", 500))
        self._delay_max.setValue(self._config.get("delay_max_ms", 1500))
        self._transfer_enabled.setChecked(self._config.get("transfer_enabled", True))
        self._transfer_delay.setValue(self._config.get("transfer_delay_ms", 1000))
        self._check_interval.setValue(self._config.get("check_interval_ms", 300))
        self._sound_enabled.setChecked(self._config.get("sound_enabled", True))
        self._schedule_enabled.setChecked(self._config.get("schedule_enabled", False))

        start = self._config.get("schedule_start", "08:00")
        end = self._config.get("schedule_end", "22:00")
        self._schedule_start.setTime(QTime.fromString(start, "HH:mm"))
        self._schedule_end.setTime(QTime.fromString(end, "HH:mm"))

        self._monitor_all.setChecked(self._config.get("monitor_all_chats", True))
        self._minimize_to_tray.setChecked(self._config.get("minimize_to_tray", True))
        self._multi_instance.setChecked(self._config.get("multi_instance", False))

        for chat in self._config.get("monitored_chats", []):
            self._chat_list.addItem(chat)

        self._on_monitor_all_toggled(self._monitor_all.isChecked())

    def _on_monitor_all_toggled(self, checked):
        self._chat_list.setEnabled(not checked)
        self._chat_input.setEnabled(not checked)

    def _add_chat(self):
        name = self._chat_input.text().strip()
        if name:
            self._chat_list.addItem(name)
            self._chat_input.clear()

    def _remove_chat(self):
        for item in self._chat_list.selectedItems():
            self._chat_list.takeItem(self._chat_list.row(item))

    def _save(self):
        if self._delay_min.value() > self._delay_max.value():
            QMessageBox.warning(self, "错误", "最小延迟不能大于最大延迟")
            return

        chats = []
        for i in range(self._chat_list.count()):
            chats.append(self._chat_list.item(i).text())

        self._config.update({
            "delay_min_ms": self._delay_min.value(),
            "delay_max_ms": self._delay_max.value(),
            "transfer_enabled": self._transfer_enabled.isChecked(),
            "transfer_delay_ms": self._transfer_delay.value(),
            "check_interval_ms": self._check_interval.value(),
            "sound_enabled": self._sound_enabled.isChecked(),
            "schedule_enabled": self._schedule_enabled.isChecked(),
            "schedule_start": self._schedule_start.time().toString("HH:mm"),
            "schedule_end": self._schedule_end.time().toString("HH:mm"),
            "monitor_all_chats": self._monitor_all.isChecked(),
            "monitored_chats": chats,
            "minimize_to_tray": self._minimize_to_tray.isChecked(),
            "multi_instance": self._multi_instance.isChecked(),
        })
        self.accept()
