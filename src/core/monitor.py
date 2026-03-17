"""微信窗口监控模块 - UI Automation"""
import logging
import ctypes
import os
import time
import re
from threading import Thread, Event

logger = logging.getLogger(__name__)

try:
    import uiautomation as auto
    HAS_UIA = True
    try:
        auto.SetGlobalSearchTimeout(1)
    except Exception:
        pass
except ImportError:
    HAS_UIA = False
    logger.warning("uiautomation不可用，监控功能将无法使用")


class WeChatMonitor:
    """微信窗口监控，仅监听已收款记录"""

    RECEIPT_KEYWORDS = ["已收款", "已被接收", "收款成功", "收款到账", "已存入零钱", "转账已收取", "转账已领取"]
    IGNORE_TEXT_KEYWORDS = [
        "[草稿]", "草稿", "消息免打扰", "已置顶", "撤销", "已领取", "已被领取", "已过期"
    ]
    IGNORE_CHAT_NAMES = []
    WECHAT_CLASSES = ("WeChatMainWndForPC", "ChatWnd", "mmui::ChatSingleWindow", "mmui::MainWindow")
    MESSAGE_TEXT_CLASSES = ("mmui::ChatTextItemView",)
    SESSION_CELL_CLASS = "mmui::ChatSessionCell"

    def __init__(self, config, on_redpacket_found=None):
        self._config = config
        self._on_redpacket_found = on_redpacket_found
        self._running = Event()
        self._thread = None
        self._wechat_windows = []
        self._seen_records = set()
        self._last_window_refresh = 0.0
        self._dll = self._load_dll()
        self._user32 = getattr(ctypes, "windll", None).user32 if os.name == "nt" else None
        self._ole32 = getattr(ctypes, "windll", None).ole32 if os.name == "nt" else None

    def _enum_wechat_hwnds(self):
        """优先用 Win32 枚举窗口，避免 UIA 根节点遍历导致的 COM 异常。"""
        if not self._user32:
            return []

        hwnds = []
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            try:
                if not self._user32.IsWindowVisible(hwnd):
                    return True

                class_buf = ctypes.create_unicode_buffer(256)
                self._user32.GetClassNameW(hwnd, class_buf, len(class_buf))
                if class_buf.value in self.WECHAT_CLASSES:
                    hwnds.append(int(hwnd))
            except Exception as e:
                logger.debug("枚举微信窗口句柄失败: %s", e)
            return True

        try:
            self._user32.EnumWindows(enum_proc(callback), 0)
        except Exception as e:
            logger.debug("EnumWindows失败: %s", e)

        return hwnds

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

            for hwnd in self._enum_wechat_hwnds():
                try:
                    ctrl = auto.ControlFromHandle(hwnd)
                    if ctrl and not any(getattr(win, "NativeWindowHandle", 0) == hwnd for win in windows):
                        windows.append(ctrl)
                except Exception as e:
                    logger.debug("句柄转UIA控件失败(%s): %s", hwnd, e)

            if not windows:
                try:
                    for class_name in self.WECHAT_CLASSES:
                        win = auto.WindowControl(searchDepth=1, ClassName=class_name)
                        if win and win.Exists(0, 0):
                            windows.append(win)
                except Exception as e:
                    logger.debug("WindowControl查找微信窗口失败: %s", e)
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
        # 常见格式: "张三: [转账] 已收款 备注"
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

        if not payer:
            for kw in self.RECEIPT_KEYWORDS:
                if kw in rest:
                    prefix = rest.split(kw, 1)[0].strip()
                    prefix = re.sub(r"(\[转账\]|\[店员消息\]|微信转账|微信收款助手)$", "", prefix).strip()
                    if prefix:
                        payer = prefix
                    break

        payer = re.sub(r"(\[转账\]|\[店员消息\]|微信转账)$", "", payer).strip()
        payer = re.sub(r"(已收款|已被接收|收款成功|收款到账)$", "", payer).strip()
        payer = re.sub(r"\d{1,2}:\d{2}$", "", payer).strip()

        for kw in self.RECEIPT_KEYWORDS:
            if kw in rest:
                after_kw = rest.split(kw, 1)[-1].strip()
                if after_kw:
                    remark = after_kw
                break

        remark = re.sub(r"^(已收款|已被接收|收款成功|收款到账|已存入零钱|转账已收取|转账已领取)\s*", "", remark).strip()
        remark = re.sub(r"^\d{1,2}:\d{2}", "", remark).strip()
        remark = re.sub(r"^(微信转账|\[转账\]|\[店员消息\])", "", remark).strip()

        return payer, remark

    def _extract_amount(self, text: str) -> float:
        text = (text or "").strip()
        for match in re.findall(r"(?:¥|￥)?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*元?", text):
            try:
                return float(match)
            except ValueError:
                continue
        return 0.0

    def _detect_event(self, text: str):
        text = (text or "").strip()
        if not text:
            return None, None
        if any(keyword in text for keyword in self.IGNORE_TEXT_KEYWORDS):
            return None, None
        for kw in self.RECEIPT_KEYWORDS:
            if kw in text:
                return "receipt", kw
        return None, None

    def _should_ignore_chat(self, chat_name: str) -> bool:
        chat_name = (chat_name or "").strip()
        return chat_name in self.IGNORE_CHAT_NAMES

    def _is_time_line(self, text: str) -> bool:
        text = (text or "").strip()
        return bool(re.match(r"^\d{1,2}:\d{2}$", text) or re.match(r"^\d{2}/\d{2}$", text))

    def _parse_session_name_block(self, name_block: str):
        """参考 1.py：解析 ChatSessionCell 的 Name 块文本。"""
        lines = [line.strip() for line in (name_block or "").splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return None

        session_name = lines[0]
        time_text = None
        for line in reversed(lines):
            if self._is_time_line(line):
                time_text = line
                break

        ignore_keywords = ["已置顶", "消息免打扰", "撤销"]
        message_line = None
        for line in lines[1:]:
            if line == time_text:
                continue
            if any(keyword in line for keyword in ignore_keywords):
                continue
            message_line = line

        if not message_line:
            return None

        sender = "我"
        content = message_line
        if ":" in message_line:
            sender, content = message_line.split(":", 1)
            sender = sender.strip().strip('"')
            content = content.strip()

        return {
            "chat_name": session_name,
            "payer": sender,
            "text": content,
            "time": time_text,
        }

    def _get_control_name(self, control):
        try:
            return (control.Name or "").strip()
        except Exception:
            return ""

    def _get_control_class(self, control):
        try:
            return (control.ClassName or "").strip()
        except Exception:
            return ""

    def _iter_descendants(self, control, depth=0, max_depth=8):
        if depth > max_depth:
            return
        yield control, depth
        try:
            for child in control.GetChildren():
                yield from self._iter_descendants(child, depth + 1, max_depth)
        except Exception:
            return

    def _get_clickable_control(self, control):
        current = control
        for _ in range(6):
            if not current:
                break
            try:
                rect = current.BoundingRectangle
                if rect and rect.right > rect.left and rect.bottom > rect.top:
                    return current
            except Exception:
                pass
            try:
                current = current.GetParentControl()
            except Exception:
                break
        return control

    def _build_result(self, control, item_name, chat_name="", chat_item=True):
        payer, remark = self._extract_sender_from_message(item_name)
        event_type, keyword = self._detect_event(item_name)
        return {
            "control": self._get_clickable_control(control),
            "text": item_name,
            "chat_item": chat_item,
            "chat_name": chat_name,
            "payer": payer,
            "remark": remark,
            "amount": self._extract_amount(item_name),
            "event_type": event_type or "receipt",
            "keyword": keyword or "",
        }

    def _scan_visible_tree(self, wechat_window):
        """递归解析当前可见控件文本，仅保留已收款记录。"""
        results = []
        seen = set()
        chat_name = self._get_current_chat_name(wechat_window)

        try:
            for ctrl, _depth in self._iter_descendants(wechat_window, max_depth=8):
                class_name = self._get_control_class(ctrl)
                item_name = self._get_control_name(ctrl)
                if not item_name:
                    continue

                event_type, matched_kw = self._detect_event(item_name)
                if not matched_kw and class_name not in self.MESSAGE_TEXT_CLASSES:
                    continue
                if class_name in self.MESSAGE_TEXT_CLASSES and not matched_kw:
                    continue
                if not matched_kw:
                    continue
                if self._should_ignore_chat(chat_name):
                    continue

                clickable = self._get_clickable_control(ctrl)
                try:
                    rect = clickable.BoundingRectangle
                    sig = f"{class_name}|{item_name}|{rect.left},{rect.top},{rect.right},{rect.bottom}"
                except Exception:
                    sig = f"{class_name}|{item_name}"

                if sig in seen:
                    continue
                seen.add(sig)

                result = self._build_result(clickable, item_name, chat_name=chat_name, chat_item=True)
                result["keyword"] = matched_kw
                result["event_type"] = event_type
                result["class_name"] = class_name
                results.append(result)
        except Exception as e:
            logger.debug("递归扫描可见控件失败: %s", e)

        return results

    def _scan_session_cells(self):
        """从 mmui::MainWindow 深层递归提取会话列表中的已收款记录。"""
        results = []
        seen = set()
        try:
            root = auto.GetRootControl()
            target = root.Control(searchDepth=5, ClassName="mmui::MainWindow")
            if not target.Exists(1):
                return results

            for ctrl, depth in self._iter_descendants(target, max_depth=14):
                if depth < 4:
                    continue
                if self._get_control_class(ctrl) != self.SESSION_CELL_CLASS:
                    continue

                block_name = self._get_control_name(ctrl)
                if not block_name:
                    continue

                parsed = self._parse_session_name_block(block_name)
                if not parsed:
                    continue
                if self._should_ignore_chat(parsed.get("chat_name", "")):
                    continue

                text = parsed.get("text", "")
                event_type, matched_kw = self._detect_event(text)
                if not matched_kw:
                    continue

                clickable = self._get_clickable_control(ctrl)
                signature = (
                    parsed.get("chat_name", ""),
                    parsed.get("payer", ""),
                    text,
                    parsed.get("time", ""),
                )
                if signature in seen:
                    continue
                seen.add(signature)

                result = {
                    "control": clickable,
                    "text": text,
                    "keyword": matched_kw,
                    "event_type": event_type,
                    "chat_item": True,
                    "chat_name": parsed.get("chat_name", ""),
                    "payer": parsed.get("payer", ""),
                    "remark": text.split(matched_kw, 1)[-1].strip() if matched_kw in text else "",
                    "time": parsed.get("time", ""),
                    "class_name": self.SESSION_CELL_CLASS,
                }
                results.append(result)
        except Exception as e:
            logger.debug("扫描ChatSessionCell失败: %s", e)
        return results

    def _scan_mmui_chat_texts(self, wechat_window):
        """参考 2025-08-26 文章思路：定向提取 mmui::ChatTextItemView 文本。"""
        results = []
        seen = set()
        chat_name = (wechat_window.Name or "").strip() or self._get_current_chat_name(wechat_window)

        try:
            for ctrl, _depth in self._iter_descendants(wechat_window, max_depth=10):
                if self._get_control_class(ctrl) not in self.MESSAGE_TEXT_CLASSES:
                    continue

                item_name = self._get_control_name(ctrl)
                if not item_name:
                    continue
                if self._should_ignore_chat(chat_name):
                    continue

                event_type, matched_kw = self._detect_event(item_name)
                if not matched_kw:
                    continue

                clickable = self._get_clickable_control(ctrl)
                try:
                    rect = clickable.BoundingRectangle
                    sig = f"{item_name}|{rect.left},{rect.top},{rect.right},{rect.bottom}"
                except Exception:
                    sig = item_name
                if sig in seen:
                    continue
                seen.add(sig)

                result = self._build_result(clickable, item_name, chat_name=chat_name, chat_item=False)
                result["keyword"] = matched_kw
                result["event_type"] = event_type
                result["class_name"] = "mmui::ChatTextItemView"
                results.append(result)
        except Exception as e:
            logger.debug("扫描mmui消息文本失败: %s", e)

        return results

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
                event_type, kw = self._detect_event(item_name)
                if kw and not self._should_ignore_chat(chat_name):
                    result = self._build_result(item, item_name, chat_name=chat_name, chat_item=False)
                    result["keyword"] = kw
                    result["event_type"] = event_type
                    results.append(result)
        except Exception as e:
            logger.debug("扫描消息失败: %s", e)
        return results

    def _scan_chat_list(self, wechat_window):
        results = []
        try:
            chat_list = wechat_window.ListControl(Name="会话")
            if not chat_list or not chat_list.Exists(0, 0):
                chat_list = wechat_window.ListControl(searchDepth=8)
                if not chat_list or not chat_list.Exists(0, 0):
                    return results
            for item in chat_list.GetChildren():
                item_name = item.Name or ""
                event_type, kw = self._detect_event(item_name)
                if kw:
                    chat_name = ""
                    try:
                        name_ctrl = item.TextControl(searchDepth=2)
                        if name_ctrl and name_ctrl.Exists(0, 0):
                            chat_name = name_ctrl.Name or ""
                        if not chat_name:
                            for child in item.GetChildren():
                                child_name = (child.Name or "").strip()
                                if child_name and kw not in child_name:
                                    chat_name = child_name
                                    break
                    except Exception:
                        pass
                    if self._should_ignore_chat(chat_name):
                        continue
                    result = self._build_result(item, item_name, chat_name=chat_name, chat_item=True)
                    result["keyword"] = kw
                    result["event_type"] = event_type
                    results.append(result)
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
        interval = max(0.2, self._config.get("check_interval_ms", 300) / 1000.0)
        initializer = None
        com_inited = False
        try:
            if HAS_UIA and hasattr(auto, "UIAutomationInitializerInThread"):
                try:
                    initializer = auto.UIAutomationInitializerInThread()
                    com_inited = True
                except Exception as e:
                    logger.debug("UIAutomationInitializerInThread初始化失败: %s", e)

            if not com_inited and self._ole32:
                try:
                    self._ole32.CoInitialize(None)
                    com_inited = True
                except Exception as e:
                    logger.debug("CoInitialize初始化失败: %s", e)

            while self._running.is_set():
                try:
                    now = time.time()
                    if not self._wechat_windows or now - self._last_window_refresh > 3:
                        self.find_wechat_windows()
                        self._last_window_refresh = now

                    all_results = []
                    all_results.extend(self._scan_session_cells())

                    for win in self._wechat_windows:
                        try:
                            if not win.Exists(0, 0):
                                continue
                        except Exception:
                            continue

                        all_results.extend(self._scan_chat_list(win))
                        all_results.extend(self._scan_messages(win))

                    emitted = set()
                    for result in all_results:
                        signature = (
                            result.get("text", ""),
                            result.get("chat_name", ""),
                            result.get("payer", ""),
                        )
                        if signature in emitted:
                            continue
                        emitted.add(signature)
                        chat_name = result.get("chat_name", "")
                        if self._should_monitor_chat(chat_name):
                            signature = (
                                result.get("chat_name", ""),
                                result.get("payer", ""),
                                result.get("text", ""),
                                result.get("time", ""),
                            )
                            if signature in self._seen_records:
                                continue
                            self._seen_records.add(signature)
                            if self._on_redpacket_found:
                                self._on_redpacket_found(result)

                except Exception as e:
                    logger.error("监控循环异常: %s", e)

                time.sleep(interval)
        finally:
            if com_inited and self._ole32:
                try:
                    self._ole32.CoUninitialize()
                except Exception:
                    pass
            initializer = None
            logger.info("监控线程停止")

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("监控已在运行")
            return
        self._running.set()
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

    @property
    def window_count(self):
        return len(self._wechat_windows)
