"""配置管理模块 - JSON读写"""
import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "disclaimer_accepted": False,
    "enabled": False,
    "delay_min_ms": 500,
    "delay_max_ms": 1500,
    "transfer_enabled": True,
    "transfer_delay_ms": 1000,
    "monitored_chats": [],
    "monitor_all_chats": True,
    "sound_enabled": True,
    "schedule_enabled": False,
    "schedule_start": "08:00",
    "schedule_end": "22:00",
    "multi_instance": False,
    "log_level": "INFO",
    "minimize_to_tray": True,
    "check_interval_ms": 100,
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".wechat_redpacket")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATS_FILE = os.path.join(CONFIG_DIR, "statistics.json")
LOG_FILE = os.path.join(CONFIG_DIR, "app.log")


class Config:
    """应用配置管理"""

    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key, default_val in DEFAULT_CONFIG.items():
                    self._data[key] = saved.get(key, default_val)
                logger.info("配置加载成功")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("配置加载失败，使用默认配置: %s", e)
                self._data = dict(DEFAULT_CONFIG)
        else:
            logger.info("未找到配置文件，使用默认配置")

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            logger.info("配置保存成功")
        except IOError as e:
            logger.error("配置保存失败: %s", e)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def update(self, data: dict):
        self._data.update(data)
        self.save()

    @property
    def data(self):
        return dict(self._data)
