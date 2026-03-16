"""收款统计面板"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QFrame,
    QLineEdit, QComboBox, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import csv


class StatsCard(QFrame):
    """统计数字卡片"""

    def __init__(self, title, value="0", parent=None):
        super().__init__(parent)
        self.setObjectName("statsCard")
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("statsTitle")
        layout.addWidget(self._title_label)

        self._value_label = QLabel(str(value))
        self._value_label.setObjectName("statsValue")
        layout.addWidget(self._value_label)

    def set_value(self, value):
        self._value_label.setText(str(value))


class StatisticsWidget(QWidget):
    """收款统计面板组件"""

    COLUMNS = ["类型", "来源", "付款人", "付款金额 (元)", "接收时间", "备注"]
    FIELD_KEYS = ["type", "source", "payer", "amount", "time", "remark"]

    def __init__(self, statistics, parent=None):
        super().__init__(parent)
        self._statistics = statistics
        self._filter_text = ""
        self._filter_field = "all"
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 统计卡片
        cards_layout = QHBoxLayout()
        self._total_count_card = StatsCard("总收款笔数")
        self._total_amount_card = StatsCard("总收款金额 (元)")
        self._today_count_card = StatsCard("今日收款笔数")
        self._today_amount_card = StatsCard("今日收款金额 (元)")

        cards_layout.addWidget(self._total_count_card)
        cards_layout.addWidget(self._total_amount_card)
        cards_layout.addWidget(self._today_count_card)
        cards_layout.addWidget(self._today_amount_card)
        layout.addLayout(cards_layout)

        # 搜索/筛选栏
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("筛选:"))

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["全部字段", "类型", "来源", "付款人", "备注"])
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_combo)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入关键词搜索...")
        self._search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self._search_input, 1)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 收款记录表格
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 类型
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 来源
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 付款人
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 金额
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 时间
        header.setSectionResizeMode(5, QHeaderView.Stretch)           # 备注
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        layout.addWidget(self._table)

        # 底部按钮
        btn_layout = QHBoxLayout()

        # 左侧: 记录数信息
        self._count_label = QLabel("共 0 条记录")
        self._count_label.setStyleSheet("color: #999; font-size: 12px;")
        btn_layout.addWidget(self._count_label)

        btn_layout.addStretch()

        export_btn = QPushButton("导出CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(refresh_btn)

        clear_btn = QPushButton("清除记录")
        clear_btn.setObjectName("dangerBtn")
        clear_btn.clicked.connect(self._clear_records)
        btn_layout.addWidget(clear_btn)

        layout.addLayout(btn_layout)

    def _on_filter_changed(self, index):
        field_map = {0: "all", 1: "type", 2: "source", 3: "payer", 4: "remark"}
        self._filter_field = field_map.get(index, "all")
        self.refresh()

    def _on_search_changed(self, text):
        self._filter_text = text.strip()
        self.refresh()

    def _filter_records(self, records):
        """根据搜索条件过滤记录"""
        if not self._filter_text:
            return records

        filtered = []
        keyword = self._filter_text.lower()
        for r in records:
            if self._filter_field == "all":
                searchable = " ".join(str(r.get(k, "")) for k in self.FIELD_KEYS)
            else:
                searchable = str(r.get(self._filter_field, ""))
            if keyword in searchable.lower():
                filtered.append(r)
        return filtered

    def refresh(self):
        """刷新统计数据和表格"""
        # 更新统计卡片
        self._total_count_card.set_value(self._statistics.total_count)
        self._total_amount_card.set_value(f"{self._statistics.total_amount:.2f}")
        today = self._statistics.today_records()
        self._today_count_card.set_value(len(today))
        self._today_amount_card.set_value(f"{self._statistics.today_amount():.2f}")

        # 过滤并更新表格
        records = self._filter_records(self._statistics.records)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(records))

        for i, record in enumerate(reversed(records)):
            # 来源
            self._table.setItem(i, 0, QTableWidgetItem(record.get("type", "红包")))
            self._table.setItem(i, 1, QTableWidgetItem(record.get("source", "")))
            # 付款人
            self._table.setItem(i, 2, QTableWidgetItem(record.get("payer", "")))
            # 付款金额
            amount_item = QTableWidgetItem()
            amount = record.get("amount", 0)
            amount_item.setData(Qt.DisplayRole, f"{amount:.2f}")
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if amount > 0:
                amount_item.setForeground(QColor("#e74c3c"))
            self._table.setItem(i, 3, amount_item)
            # 接收时间
            self._table.setItem(i, 4, QTableWidgetItem(record.get("time", "")))
            # 备注
            self._table.setItem(i, 5, QTableWidgetItem(record.get("remark", "")))

        self._table.setSortingEnabled(True)
        self._count_label.setText(f"共 {len(records)} 条记录")

    def _export_csv(self):
        """导出收款记录为CSV"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出收款记录", "收款记录.csv",
            "CSV文件 (*.csv);;所有文件 (*)"
        )
        if not path:
            return

        try:
            records = self._filter_records(self._statistics.records)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(self.COLUMNS)
                for r in records:
                    writer.writerow([
                        r.get("type", "红包"),
                        r.get("source", ""),
                        r.get("payer", ""),
                        f"{r.get('amount', 0):.2f}",
                        r.get("time", ""),
                        r.get("remark", ""),
                    ])
            QMessageBox.information(self, "导出成功", f"已导出 {len(records)} 条记录到:\n{path}")
        except IOError as e:
            QMessageBox.warning(self, "导出失败", f"写入文件失败: {e}")

    def _clear_records(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有收款记录吗？此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._statistics.clear()
            self.refresh()
