"""红包抢夺逻辑模块"""
import logging
import random
import time
import ctypes
import os
from threading import Lock

logger = logging.getLogger(__name__)

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False


class RedPacketGrabber:
    """红包抢夺执行器"""

    def __init__(self, config, statistics, on_grab_success=None):
        self._config = config
        self._statistics = statistics
        self._on_grab_success = on_grab_success
        self._lock = Lock()
        self._grabbed_set = set()
        self._dll = self._load_dll()

    def _load_dll(self):
        dll_path = os.path.join(os.path.dirname(__file__), "..", "native", "fast_click.dll")
        dll_path = os.path.abspath(dll_path)
        if os.path.exists(dll_path):
            try:
                dll = ctypes.CDLL(dll_path)
                logger.info("Grabber: fast_click.dll加载成功")
                return dll
            except OSError as e:
                logger.warning("Grabber: DLL加载失败: %s", e)
        return None

    def _get_delay(self):
        min_ms = self._config.get("delay_min_ms", 500)
        max_ms = self._config.get("delay_max_ms", 1500)
        return random.randint(min_ms, max_ms) / 1000.0

    def _fast_click(self, x, y):
        if self._dll:
            try:
                self._dll.fast_click(int(x), int(y))
                return True
            except Exception as e:
                logger.debug("DLL点击失败: %s", e)
        if HAS_UIA:
            auto.Click(int(x), int(y))
            return True
        return False

    def _generate_packet_id(self, result: dict) -> str:
        text = result.get("text", "")
        return f"{text}_{id(result.get('control'))}"

    def grab(self, redpacket_info: dict):
        """执行抢红包操作"""
        with self._lock:
            packet_id = self._generate_packet_id(redpacket_info)
            if packet_id in self._grabbed_set:
                logger.debug("红包已处理，跳过: %s", packet_id)
                return False
            self._grabbed_set.add(packet_id)

        control = redpacket_info.get("control")
        if not control:
            logger.warning("无效的红包控件")
            return False

        # 提取来源信息，通过参数传递（避免实例变量竞争）
        info = {
            "chat_name": redpacket_info.get("chat_name", ""),
            "payer": redpacket_info.get("payer", ""),
            "remark": redpacket_info.get("remark", ""),
        }

        try:
            delay = self._get_delay()
            logger.info("等待 %.1f 秒后抢红包...", delay)
            time.sleep(delay)

            if redpacket_info.get("chat_item"):
                self._click_control(control)
                time.sleep(0.3)
                return self._grab_in_current_chat(info)

            self._click_control(control)
            time.sleep(0.3)
            return self._click_open_button(info)

        except Exception as e:
            logger.error("抢红包失败: %s", e)
            return False

    def _click_control(self, control):
        try:
            rect = control.BoundingRectangle
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            self._fast_click(cx, cy)
        except Exception:
            try:
                control.Click()
            except Exception as e:
                logger.error("点击控件失败: %s", e)

    def _click_open_button(self, info):
        try:
            time.sleep(0.5)
            desktop = auto.GetRootControl()
            for win in desktop.GetChildren():
                if "红包" in (win.Name or ""):
                    open_btn = win.ButtonControl(Name="开")
                    if not open_btn.Exists(0, 0):
                        open_btn = win.ButtonControl(searchDepth=5)
                    if open_btn.Exists(0, 0):
                        self._click_control(open_btn)
                        logger.info("成功点击'开'按钮")
                        self._on_success(win, info)
                        return True

            open_btn = auto.ButtonControl(Name="开", searchDepth=3)
            if open_btn.Exists(1, 1):
                self._click_control(open_btn)
                logger.info("成功点击'开'按钮(备选)")
                self._on_success(None, info)
                return True

            logger.warning("未找到'开'按钮，可能红包已被领完")
            return False

        except Exception as e:
            logger.error("点击'开'按钮失败: %s", e)
            return False

    def _grab_in_current_chat(self, info):
        try:
            desktop = auto.GetRootControl()
            for win in desktop.GetChildren():
                if win.ClassName == "WeChatMainWndForPC":
                    msg_list = win.ListControl(Name="消息")
                    if msg_list.Exists(0, 0):
                        children = msg_list.GetChildren()
                        for item in reversed(children):
                            name = item.Name or ""
                            if any(kw in name for kw in ["微信红包", "领取红包"]):
                                self._click_control(item)
                                time.sleep(0.3)
                                return self._click_open_button(info)
        except Exception as e:
            logger.error("在当前聊天抢红包失败: %s", e)
        return False

    def _on_success(self, win, info):
        """抢包成功后处理，记录完整收款信息"""
        amount = 0.0
        source = info.get("chat_name", "") or "未知来源"
        payer = info.get("payer", "") or "未知"
        remark = info.get("remark", "")

        # 尝试从结果页面读取金额和备注
        try:
            if win:
                time.sleep(0.5)
                texts = []
                for ctrl in win.GetChildren():
                    if ctrl.Name:
                        texts.append(ctrl.Name)
                for t in texts:
                    cleaned = t.replace("元", "").replace("¥", "").strip()
                    try:
                        amount = float(cleaned)
                        break
                    except ValueError:
                        continue
                # 尝试从弹窗文本中提取更多信息
                for t in texts:
                    if not remark and "恭喜" not in t and "元" not in t and len(t) > 1:
                        if t not in (payer, source):
                            remark = t
        except Exception:
            pass

        record = self._statistics.add_record(
            amount=amount,
            source=source,
            payer=payer,
            remark=remark,
        )
        if self._on_grab_success:
            self._on_grab_success(record)

    def clear_grabbed_cache(self):
        self._grabbed_set.clear()
