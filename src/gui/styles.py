"""QSS样式定义"""

MAIN_STYLE = """
QMainWindow {
    background-color: #f5f5f5;
}

QWidget#centralWidget {
    background-color: #f5f5f5;
}

/* 顶部状态栏 */
QFrame#statusBar {
    background-color: #07c160;
    border-radius: 8px;
    padding: 12px;
}

QLabel#statusLabel {
    color: white;
    font-size: 16px;
    font-weight: bold;
}

/* 开关按钮 */
QPushButton#toggleBtn {
    background-color: #07c160;
    color: white;
    border: none;
    border-radius: 20px;
    padding: 10px 30px;
    font-size: 16px;
    font-weight: bold;
    min-width: 120px;
    min-height: 40px;
}

QPushButton#toggleBtn:hover {
    background-color: #06ad56;
}

QPushButton#toggleBtn[running="true"] {
    background-color: #e74c3c;
}

QPushButton#toggleBtn[running="true"]:hover {
    background-color: #c0392b;
}

/* 统计卡片 */
QFrame#statsCard {
    background-color: white;
    border-radius: 8px;
    padding: 16px;
    border: 1px solid #e0e0e0;
}

QLabel#statsTitle {
    font-size: 13px;
    color: #999;
}

QLabel#statsValue {
    font-size: 24px;
    font-weight: bold;
    color: #333;
}

/* 日志区域 */
QTextEdit#logView {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 8px;
    font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 12px;
    color: #333;
}

/* 通用按钮 */
QPushButton {
    background-color: #07c160;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #06ad56;
}

QPushButton:pressed {
    background-color: #059a4c;
}

QPushButton#dangerBtn {
    background-color: #e74c3c;
}

QPushButton#dangerBtn:hover {
    background-color: #c0392b;
}

/* 设置面板 */
QGroupBox {
    font-size: 14px;
    font-weight: bold;
    color: #333;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 10px;
    padding: 16px;
    padding-top: 28px;
    background-color: white;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QSpinBox, QTimeEdit, QLineEdit {
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 6px;
    font-size: 13px;
    background-color: white;
}

QSpinBox:focus, QTimeEdit:focus, QLineEdit:focus {
    border-color: #07c160;
}

QCheckBox {
    font-size: 13px;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}

/* 列表 */
QListWidget {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background-color: white;
    font-size: 13px;
}

QListWidget::item {
    padding: 6px;
}

QListWidget::item:selected {
    background-color: #e8f5e9;
    color: #333;
}

/* 表格 */
QTableWidget {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background-color: white;
    gridline-color: #f0f0f0;
    font-size: 12px;
}

QTableWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #f9f9f9;
    border: none;
    border-bottom: 1px solid #e0e0e0;
    padding: 8px;
    font-weight: bold;
    font-size: 12px;
}

/* 免责声明 */
QDialog#disclaimerDialog {
    background-color: white;
}

QTextBrowser#disclaimerText {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.6;
}
"""
