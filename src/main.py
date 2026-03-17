"""微信收款监听工具 - 程序入口"""
import sys
import os
import logging

# 将src目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from core.config import Config, LOG_FILE, CONFIG_DIR
from gui.disclaimer_dialog import DisclaimerDialog
from gui.main_window import MainWindow


def setup_logging():
    """配置日志"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("程序启动")

    # 高DPI适配
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("微信收款监听工具")

    # 检查免责声明
    config = Config()
    if not config.get("disclaimer_accepted"):
        dlg = DisclaimerDialog()
        if dlg.exec_() and dlg.is_accepted:
            config.update({"disclaimer_accepted": True})
            logger.info("用户已同意免责声明")
        else:
            logger.info("用户未同意免责声明，退出")
            sys.exit(0)

    # 显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
