"""红包抢夺逻辑模块"""
import logging
import random
import time
import ctypes
import os
import re
from threading import Lock

logger = logging.getLogger(__name__)

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False


class RedPacketGrabber:
    """红包抢夺执行器"""
    WECHAT_CLASSES = ("WeChatMainWndForPC", "ChatWnd", "mmui::ChatSingleWindow")
    RED_PACKET_KEYWORDS = ("微信红包", "领取红包", "恭喜发财")
    TRANSFER_KEYWORDS = ("微信转账", "转账给你", "请收款", "待收款", "向你转账", "收款")
    TRANSFER_BUTTON_NAMES = ("收款", "确认收款", "立即收款", "接受转账", "确认", "收下")

    def __init__(self, config, statistics, on_grab_success=None):
        self._config = config
        self._statistics = statistics
        self._on_grab_success = on_grab_success
        self._lock = Lock()
        self._grabbed_set = set()
        self._dll = self._load_dll()
        self._user32 = getattr(ctypes, "windll", None).user32 if os.name == "nt" else None
        self._success_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "success_logs"))
        os.makedirs(self._success_log_dir, exist_ok=True)

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

    def _get_transfer_delay(self):
        return max(0, self._config.get("transfer_delay_ms", 1000)) / 1000.0

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

    def _bring_window_to_front(self, control=None):
        hwnd = 0
        try:
            if control:
                hwnd = int(getattr(control, "NativeWindowHandle", 0) or 0)
                if not hwnd:
                    top = control.GetTopLevelControl()
                    hwnd = int(getattr(top, "NativeWindowHandle", 0) or 0)
        except Exception:
            hwnd = 0

        if not hwnd:
            windows = self._enum_window_controls(class_name=self.WECHAT_CLASSES)
            if windows:
                hwnd = int(getattr(windows[0], "NativeWindowHandle", 0) or 0)

        if not hwnd:
            return False

        try:
            if self._dll and hasattr(self._dll, "bring_to_front"):
                self._dll.bring_to_front(ctypes.c_void_p(hwnd))
                return True
            if self._user32:
                self._user32.SetForegroundWindow(hwnd)
                return True
        except Exception as e:
            logger.debug("窗口前置失败: %s", e)
        return False

    def _generate_packet_id(self, result: dict) -> str:
        text = result.get("text", "")
        chat_name = result.get("chat_name", "")
        payer = result.get("payer", "")
        rect_sig = ""
        control = result.get("control")
        if control:
            try:
                rect = control.BoundingRectangle
                rect_sig = f"{rect.left},{rect.top},{rect.right},{rect.bottom}"
            except Exception:
                pass
        return f"{chat_name}_{payer}_{text}_{rect_sig}"

    def _enum_window_controls(self, class_name=None):
        if not self._user32 or not HAS_UIA:
            return []

        hwnds = []
        controls = []
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def callback(hwnd, _lparam):
            try:
                if not self._user32.IsWindowVisible(hwnd):
                    return True

                class_buf = ctypes.create_unicode_buffer(256)
                self._user32.GetClassNameW(hwnd, class_buf, len(class_buf))
                if class_name:
                    if isinstance(class_name, (tuple, list, set)):
                        if class_buf.value not in class_name:
                            return True
                    elif class_buf.value != class_name:
                        return True

                hwnds.append(int(hwnd))
            except Exception as e:
                logger.debug("枚举窗口失败: %s", e)
            return True

        try:
            self._user32.EnumWindows(enum_proc(callback), 0)
        except Exception as e:
            logger.debug("EnumWindows失败: %s", e)

        for hwnd in hwnds:
            try:
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl:
                    controls.append(ctrl)
            except Exception as e:
                logger.debug("ControlFromHandle失败(%s): %s", hwnd, e)
        return controls

    def _iter_descendants(self, control, depth=0, max_depth=10):
        if depth > max_depth:
            return
        yield control
        try:
            for child in control.GetChildren():
                yield from self._iter_descendants(child, depth + 1, max_depth)
        except Exception:
            return

    def _find_named_control(self, root, names, max_depth=10):
        target_names = {name.strip() for name in names}
        for ctrl in self._iter_descendants(root, max_depth=max_depth):
            try:
                ctrl_name = (ctrl.Name or "").strip()
                if ctrl_name in target_names:
                    rect = ctrl.BoundingRectangle
                    if rect and rect.right > rect.left and rect.bottom > rect.top:
                        return ctrl
            except Exception:
                continue
        return None

    def _get_top_level_control(self, control):
        if not control:
            return None
        try:
            return control.GetTopLevelControl()
        except Exception:
            return control

    def _get_foreground_window_control(self):
        try:
            if self._user32:
                hwnd = self._user32.GetForegroundWindow()
                if hwnd:
                    return auto.ControlFromHandle(hwnd)
        except Exception as e:
            logger.debug("获取前台窗口失败: %s", e)
        return None

    def _get_search_roots(self, control=None):
        roots = []
        top = self._get_top_level_control(control)
        if top:
            roots.append(top)

        fg = self._get_foreground_window_control()
        if fg:
            fg_hwnd = int(getattr(fg, "NativeWindowHandle", 0) or 0)
            if not any(int(getattr(r, "NativeWindowHandle", 0) or 0) == fg_hwnd for r in roots):
                roots.append(fg)

        for win in self._enum_window_controls(class_name=self.WECHAT_CLASSES):
            hwnd = int(getattr(win, "NativeWindowHandle", 0) or 0)
            if not any(int(getattr(r, "NativeWindowHandle", 0) or 0) == hwnd for r in roots):
                roots.append(win)
        return roots

    def _append_success_log(self, record_type, source, payer, amount, remark):
        try:
            os.makedirs(self._success_log_dir, exist_ok=True)
            log_path = os.path.join(self._success_log_dir, time.strftime("%Y-%m-%d") + ".txt")
            line = (
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} | 类型={record_type} | 来源={source} | "
                f"付款人={payer} | 金额={amount:.2f} | 备注={remark}\n"
            )
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.warning("写入成功日志失败: %s", e)

    def _collect_all_texts(self, root, max_depth=8):
        texts = []
        try:
            for ctrl in self._iter_descendants(root, max_depth=max_depth):
                name = (getattr(ctrl, "Name", "") or "").strip()
                if name:
                    texts.append(name)
        except Exception:
            pass
        return texts

    def _clean_text(self, text):
        return re.sub(r"\s+", " ", (text or "").strip())

    def _extract_remark_from_info(self, info):
        text = self._clean_text(info.get("text", ""))
        if not text:
            return ""

        patterns = [
            r"(?:微信红包|\[微信红包\]|领取红包|恭喜发财)\s*(.+)$",
            r"(?:微信转账|\[转账\]|转账给你|请收款|待收款|向你转账)\s*(.+)$",
            r"(?:留言|备注)[:：]\s*(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                remark = self._clean_text(match.group(1))
                remark = re.sub(r"^(已收款|请收款|待收款)\s*", "", remark).strip()
                if remark and remark not in self.TRANSFER_BUTTON_NAMES:
                    return remark
        return ""

    def _extract_remark_from_texts(self, texts, payer, source, event_type):
        ignore = {
            "", payer, source, "红包", "微信红包", "领取红包", "开", "拆红包",
            "立即领取", "收款", "确认收款", "转账", "微信转账", "已收款",
        }
        candidates = []
        for text in texts:
            clean = self._clean_text(text)
            if not clean or clean in ignore:
                continue
            if re.search(r"(¥|￥|元|^\d+(?:\.\d{1,2})?$)", clean):
                continue
            if clean in self.TRANSFER_BUTTON_NAMES:
                continue
            if len(clean) <= 1:
                continue

            msg = re.search(r"(?:留言|备注)[:：]\s*(.+)$", clean)
            if msg:
                clean = self._clean_text(msg.group(1))
            if clean and clean not in ignore:
                candidates.append(clean)

        for candidate in candidates:
            if event_type == "redpacket" and any(kw in candidate for kw in ["恭喜", "发财", "红包"]):
                return candidate
        if candidates:
            return candidates[0]
        return ""

    def grab(self, redpacket_info: dict):
        """执行红包/转账处理"""
        with self._lock:
            packet_id = self._generate_packet_id(redpacket_info)
            if packet_id in self._grabbed_set:
                logger.debug("消息已处理，跳过: %s", packet_id)
                return False
            self._grabbed_set.add(packet_id)

        control = redpacket_info.get("control")
        if not control:
            logger.warning("无效的消息控件")
            return False

        # 提取来源信息，通过参数传递（避免实例变量竞争）
        info = {
            "chat_name": redpacket_info.get("chat_name", ""),
            "payer": redpacket_info.get("payer", ""),
            "remark": redpacket_info.get("remark", ""),
            "event_type": redpacket_info.get("event_type", "redpacket"),
            "text": redpacket_info.get("text", ""),
            "root_control": self._get_top_level_control(control),
        }

        try:
            if info["event_type"] == "transfer":
                delay = self._get_transfer_delay()
                logger.info("等待 %.1f 秒后收款...", delay)
            else:
                delay = self._get_delay()
                logger.info("等待 %.1f 秒后抢红包...", delay)
            time.sleep(delay)

            if not self._click_control(control):
                logger.warning("点击消息入口失败: %s", info.get("text", ""))
                return False
            logger.info("已点击消息入口: %s", info.get("text", ""))
            time.sleep(0.3)
            if info["event_type"] == "transfer":
                if redpacket_info.get("chat_item"):
                    if self._receive_transfer_in_current_chat(info):
                        return True
                    return self._click_receive_transfer_button(info)
                if self._click_receive_transfer_button(info):
                    return True
                return self._receive_transfer_in_current_chat(info)

            if redpacket_info.get("chat_item"):
                if self._grab_in_current_chat(info):
                    return True
                return self._click_open_button(info)

            if self._click_open_button(info):
                return True
            return self._grab_in_current_chat(info)

        except Exception as e:
            logger.error("抢红包失败: %s", e)
            return False

    def _click_control(self, control):
        try:
            self._bring_window_to_front(control)
            rect = control.BoundingRectangle
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            if self._fast_click(cx, cy):
                return True
        except Exception:
            pass
        try:
            control.Click()
            return True
        except Exception:
            pass
        try:
            control.DoubleClick()
            return True
        except Exception as e:
            logger.error("点击控件失败: %s", e)
            return False

    def _click_open_button(self, info):
        try:
            time.sleep(0.5)
            for win in self._get_search_roots(info.get("root_control")):
                win_name = win.Name or ""
                win_class = getattr(win, "ClassName", "") or ""
                if "红包" in win_name or "Red Packet" in win_name or win_class in self.WECHAT_CLASSES:
                    open_btn = self._find_named_control(win, ("开", "拆红包", "领取红包", "立即领取"), max_depth=12)
                    if open_btn and self._click_control(open_btn):
                        logger.info("成功点击红包确认按钮")
                        self._on_success(win, info)
                        return True

            for btn_name in ("开", "拆红包", "领取红包", "立即领取"):
                open_btn = auto.ButtonControl(Name=btn_name, searchDepth=6)
                if open_btn.Exists(1, 1) and self._click_control(open_btn):
                    logger.info("成功点击红包确认按钮(备选): %s", btn_name)
                    self._on_success(None, info)
                    return True

            logger.warning("未找到红包确认按钮，可能红包已被领完或按钮结构已变化")
            return False

        except Exception as e:
            logger.error("点击'开'按钮失败: %s", e)
            return False

    def _extract_amount_from_texts(self, texts):
        for text in texts:
            for match in re.findall(r"(?:¥|￥)?\s*([0-9]+(?:\.[0-9]{1,2})?)\s*元?", text):
                try:
                    return float(match)
                except ValueError:
                    continue
        return 0.0

    def _click_receive_transfer_button(self, info):
        try:
            time.sleep(0.5)
            for win in self._get_search_roots(info.get("root_control")):
                texts = []
                try:
                    for child in self._iter_descendants(win, max_depth=6):
                        if child.Name:
                            texts.append(child.Name)
                except Exception:
                    pass
                joined = " ".join(texts) + " " + (win.Name or "")
                if not any(kw in joined for kw in self.TRANSFER_KEYWORDS):
                    continue

                btn = self._find_named_control(win, ("收款",), max_depth=14)
                if btn and self._click_control(btn):
                    logger.info("成功点击转账收款按钮: 收款")
                    self._on_success(win, info)
                    return True

                btn = self._find_named_control(win, self.TRANSFER_BUTTON_NAMES, max_depth=14)
                if btn and self._click_control(btn):
                    logger.info("成功点击转账收款按钮: %s", btn.Name or "")
                    self._on_success(win, info)
                    return True

                for btn_name in ("收款",) + tuple(name for name in self.TRANSFER_BUTTON_NAMES if name != "收款"):
                    btn = win.ButtonControl(Name=btn_name, searchDepth=10)
                    if btn.Exists(0, 0) and self._click_control(btn):
                        logger.info("成功点击转账收款按钮(备选): %s", btn_name)
                        self._on_success(win, info)
                        return True
            return False
        except Exception as e:
            logger.error("点击转账收款按钮失败: %s", e)
            return False

    def _grab_in_current_chat(self, info):
        try:
            for win in self._get_search_roots(info.get("root_control")):
                msg_list = win.ListControl(Name="消息")
                if not msg_list.Exists(0, 0):
                    msg_list = win.ListControl(searchDepth=8)
                if msg_list.Exists(0, 0):
                    children = msg_list.GetChildren()
                    for item in reversed(children):
                        name = item.Name or ""
                        if any(kw in name for kw in ["微信红包", "领取红包", "恭喜发财"]):
                            if not self._click_control(item):
                                continue
                            logger.info("已进入当前聊天中的红包消息")
                            time.sleep(0.3)
                            return self._click_open_button(info)
        except Exception as e:
            logger.error("在当前聊天抢红包失败: %s", e)
        return False

    def _receive_transfer_in_current_chat(self, info):
        try:
            for win in self._get_search_roots(info.get("root_control")):
                msg_list = win.ListControl(Name="消息")
                if not msg_list.Exists(0, 0):
                    msg_list = win.ListControl(searchDepth=10)
                if msg_list.Exists(0, 0):
                    children = msg_list.GetChildren()
                    for item in reversed(children):
                        name = item.Name or ""
                        if any(kw in name for kw in self.TRANSFER_KEYWORDS):
                            if not self._click_control(item):
                                continue
                            logger.info("已进入当前聊天中的转账消息")
                            time.sleep(0.3)
                            if self._click_receive_transfer_button(info):
                                return True
        except Exception as e:
            logger.error("在当前聊天收款失败: %s", e)
        return False

    def _on_success(self, win, info):
        """收款成功后处理，记录完整收款信息"""
        amount = 0.0
        source = info.get("chat_name", "") or "未知来源"
        payer = info.get("payer", "") or "未知"
        remark = self._clean_text(info.get("remark", ""))
        event_type = info.get("event_type", "redpacket")
        record_type = "转账" if event_type == "transfer" else "红包"

        # 尝试从结果页面读取金额和备注
        try:
            if win:
                time.sleep(0.5)
                texts = self._collect_all_texts(win, max_depth=10)
                amount = self._extract_amount_from_texts(texts)
                if not remark:
                    remark = self._extract_remark_from_texts(texts, payer, source, event_type)
        except Exception:
            pass

        if not amount:
            amount = self._extract_amount_from_texts([info.get("text", ""), remark])
        if not remark:
            remark = self._extract_remark_from_info(info)
        if not remark and info.get("text"):
            raw_text = self._clean_text(info.get("text", ""))
            raw_text = re.sub(r"^(?:.+?:\s*)?", "", raw_text).strip()
            for prefix in ("[微信红包]", "微信红包", "领取红包", "恭喜发财", "[转账]", "微信转账", "转账给你", "请收款", "待收款", "向你转账"):
                if raw_text.startswith(prefix):
                    raw_text = raw_text[len(prefix):].strip()
            if raw_text and raw_text not in self.TRANSFER_BUTTON_NAMES:
                remark = raw_text

        record = self._statistics.add_record(
            amount=amount,
            source=source,
            payer=payer,
            remark=remark,
            record_type=record_type,
        )
        self._append_success_log(record_type, source, payer, amount, remark)
        logger.info("已写入收款记录: 类型=%s 来源=%s 付款人=%s 金额=%.2f", record_type, source, payer, amount)
        if self._on_grab_success:
            self._on_grab_success(record)

    def clear_grabbed_cache(self):
        self._grabbed_set.clear()
