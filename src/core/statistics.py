"""金额统计模块"""
import json
import os
import logging
from datetime import datetime

from .config import STATS_FILE

logger = logging.getLogger(__name__)


class Statistics:
    """红包收款记录统计"""

    def __init__(self):
        self._records = []
        self.load()

    def load(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
                logger.info("统计数据加载成功，共%d条记录", len(self._records))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("统计数据加载失败: %s", e)
                self._records = []

    def save(self):
        try:
            with open(STATS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error("统计数据保存失败: %s", e)

    def add_record(self, amount: float, source: str, payer: str, remark: str = "", record_type: str = "红包"):
        """添加收款记录

        Args:
            amount: 付款金额
            source: 来源（群聊名称/私聊名称）
            payer: 付款人昵称
            remark: 红包备注（如"恭喜发财"等）
        """
        record = {
            "type": record_type,
            "source": source,
            "payer": payer,
            "amount": amount,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "remark": remark,
        }
        self._records.append(record)
        self.save()
        logger.info(
            "收款记录[%s]: %.2f元 | 来源: %s | 付款人: %s | 备注: %s",
            record_type, amount, source, payer, remark
        )
        return record

    @property
    def records(self):
        return list(self._records)

    @property
    def total_amount(self):
        return sum(r.get("amount", 0) for r in self._records)

    @property
    def total_count(self):
        return len(self._records)

    def today_records(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return [r for r in self._records if r.get("time", "").startswith(today)]

    def today_amount(self):
        return sum(r.get("amount", 0) for r in self.today_records())

    def clear(self):
        self._records = []
        self.save()
