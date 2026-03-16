"""定时开关调度模块"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Scheduler:
    """根据配置的时间范围自动开关抢包功能"""

    def __init__(self, config):
        self._config = config

    def is_in_schedule(self) -> bool:
        """检查当前时间是否在调度范围内"""
        if not self._config.get("schedule_enabled"):
            return True  # 未启用定时则始终允许

        now = datetime.now().time()
        try:
            start = datetime.strptime(self._config.get("schedule_start", "08:00"), "%H:%M").time()
            end = datetime.strptime(self._config.get("schedule_end", "22:00"), "%H:%M").time()
        except ValueError:
            logger.warning("定时配置格式错误，默认允许运行")
            return True

        if start <= end:
            return start <= now <= end
        else:
            # 跨午夜，如 22:00 - 06:00
            return now >= start or now <= end

    def should_run(self) -> bool:
        """综合判断是否应该运行"""
        return self._config.get("enabled", False) and self.is_in_schedule()
