"""微信窗口监控模块 - UI Automation"""
import logging
import ctypes
import os
import time
from threading import Thread, Event

logger = logging.getLogger(__name__)

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False
    logger.warning("uiautomation不可用，监控功能将无法使用")


class WeChatMonitor:
    """微信窗口监控，检测红包消息"""

    RED_PACKET_KEYWORDS = ["微信红包", "[微信红包]", "领取红包", "恭喜发财"]
    WECHAT_CLASS = "WeChatMainWndForPC"

    def __init__(self, config, on_redpacket_found=None):
        self._config = config
        self._on_redpacket_found = on_redpacket_found
        self._running = Event()
        self._thread = None
        self._wechat_windows = []
        self._dll = self._load_dll()

    def _load_dll(self):
        dll_path = os.path.join(os.path.dirname(__file__), "..", "native", "fast_click.dll")
        dll_path = os.path.abspath(dll_path)
        if os.path.exists(dll_path):
            try:
                dll = ctypes.CDLL(dll_path)
                logger.info("fast_click.dll加载成功")
                return dll
            except OSError as e:
                logger.warning("DLL加载失败: %s", e)
        return None

    def find_wechat_windows(self):
        if not HAS_UIA:
            return []
        windows = []
        try:
            if self._dll:
                hwnd = self._dll.find_wechat_window()
                if hwnd:
                    try:
                        ctrl = auto.ControlFromHandle(hwnd)
                        if ctrl:
                            windows.append(ctrl)
                    except Exception:
                        pass

            if not windows:
                desktop = auto.GetRootControl()
                for win in desktop.GetChildren():
                    if win.ClassName == self.WECHAT_CLASS:
                        windows.append(win)
        except Exception as e:
            logger.error("查找微信窗口失败: %s", e)

        self._wechat_windows = windows
        logger.info("找到%d个微信窗口", len(windows))
        return windows

    def _get_current_chat_name(self, wechat_window):
        """获取当前聊天窗口的名称（群名/联系人名）"""
        try:
            # 微信顶部显示当前聊天对象名称
            title_bar = wechat_window.TextControl(searchDepth=5)
            if title_bar and title_bar.Exists(0, 0):
                name = title_bar.Name or ""
                # 排除非聊天名称的文本
                if name and name not in ("微信", "WeChat"):
                    return name
        except Exception:
            pass
        return ""

    def _extract_sender_from_message(self, item_name: str):
        """从消息文本中提取发送者和备注"""
        payer = ""
        remark = ""
        # 常见格式: "张三: [微信红包] 恭喜发财"
        if ": " in item_name:
            parts = item_name.split(": ", 1)
            payer = parts[0].strip()
            rest = parts[1] if len(parts) > 1 else ""
        elif ":" in item_name:
            parts = item_name.split(":", 1)
            payer = parts[0].strip()
            rest = parts[1] if len(parts) > 1 else ""
        else:
            rest = item_name

        # 提取备注（红包祝福语）
        for kw in self.RED_PACKET_KEYWORDS:
            if kw in rest:
                after_kw = rest.split(kw, 1)[-1].strip()
                if after_kw:
                    remark = after_kw
                break

        return payer, remark

    def _scan_messages(self, wechat_window):
        results = []
        try:
            chat_name = self._get_current_chat_name(wechat_window)
            msg_list = wechat_window.ListControl(Name="消息")
            if not msg_list.Exists(0, 0):
                msg_list = wechat_window.ListControl(searchDepth=5)
                if not msg_list or not msg_list.Exists(0, 0):
                    return results

            for item in msg_list.GetChildren():
                item_name = item.Name or ""
                for kw in self.RED_PACKET_KEYWORDS:
                    if kw in item_name:
                        payer, remark = self._extract_sender_from_message(item_name)
                        results.append({
                            "control": item,
                            "text": item_name,
                            "keyword": kw,
                            "chat_name": chat_name,
                            "payer": payer,
                            "remark": remark,
                        })
                        break
        except Exception as e:
            logger.debug("扫描消息失败: %s", e)
        return results

    def _scan_chat_list(self, wechat_window):
        results = []
        try:
            chat_list = wechat_window.ListControl(Name="会话")
            if not chat_list or not chat_list.Exists(0, 0):
                return results
            for item in chat_list.GetChildren():
                item_name = item.Name or ""
                for kw in self.RED_PACKET_KEYWORDS:
                    if kw in item_name:
                        # 聊天列表项：名称就是来源
                        payer, remark = self._extract_sender_from_message(item_name)
                        # 从列表项获取群名/联系人名
                        chat_name = ""
                        try:
                            # 列表项的第一个文本控件通常是联系人/群名
                            name_ctrl = item.TextControl(searchDepth=2)
                            if name_ctrl and name_ctrl.Exists(0, 0):
                                chat_name = name_ctrl.Name or ""
                        except Exception:
                            pass
                        results.append({
                            "control": item,
                            "text": item_name,
                            "chat_item": True,
                            "chat_name": chat_name,
                            "payer": payer,
                            "remark": remark,
                        })
                        break
        except Exception as e:
            logger.debug("扫描聊天列表失败: %s", e)
        return results

    def _should_monitor_chat(self, chat_name: str) -> bool:
        if self._config.get("monitor_all_chats"):
            return True
        monitored = self._config.get("monitored_chats", [])
        return chat_name in monitored

    def _monitor_loop(self):
        logger.info("监控线程启动")
        interval = self._config.get("check_interval_ms", 300) / 1000.0

        while self._running.is_set():
            try:
                if not self._wechat_windows:
                    self.find_wechat_windows()

                for win in self._wechat_windows:
                    try:
                        if not win.Exists(0, 0):
                            continue
                    except Exception:
                        continue

                    chat_results = self._scan_chat_list(win)
                    for result in chat_results:
                        chat_name = result.get("chat_name", "")
                        if self._should_monitor_chat(chat_name):
                            if self._on_redpacket_found:
                                self._on_redpacket_found(result)

                    msg_results = self._scan_messages(win)
                    for result in msg_results:
                        chat_name = result.get("chat_name", "")
                        if self._should_monitor_chat(chat_name):
                            if self._on_redpacket_found:
                                self._on_redpacket_found(result)

            except Exception as e:
                logger.error("监控循环异常: %s", e)

            time.sleep(interval)

        logger.info("监控线程停止")

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("监控已在运行")
            return
        self._running.set()
        self.find_wechat_windows()
        self._thread = Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("微信监控已启动")

    def stop(self):
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=3)
        self._wechat_windows = []
        logger.info("微信监控已停止")

    @property
    def is_running(self):
        return self._running.is_set()
