"""免责声明弹窗"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QPushButton, QCheckBox, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

DISCLAIMER_TEXT = """
<h2 style="text-align:center;">免责声明</h2>
<p>在使用本工具（"微信自动抢红包工具"）之前，请仔细阅读以下免责声明：</p>

<h3>1. 使用目的</h3>
<p>本工具仅供学习交流、商业收款及经授权的自动化场景使用。用户应确保其使用场景符合相关法律法规及微信平台的服务条款。</p>

<h3>2. 风险提示</h3>
<ul>
<li>使用本工具可能违反微信的用户协议，导致账号被限制或封禁。</li>
<li>开发者不对因使用本工具造成的任何账号风险、财产损失或其他不利后果承担责任。</li>
<li>本工具依赖微信PC端界面结构，微信更新后可能失效。</li>
</ul>

<h3>3. 免责条款</h3>
<ul>
<li>本工具按"原样"提供，不提供任何明示或暗示的保证。</li>
<li>开发者不对本工具的可用性、准确性、可靠性或适用性做任何承诺。</li>
<li>用户因使用本工具产生的一切后果由用户自行承担。</li>
</ul>

<h3>4. 法律合规</h3>
<p>用户应遵守所在国家/地区的法律法规。如本工具的使用违反当地法律，用户应立即停止使用。</p>

<h3>5. 知识产权</h3>
<p>"微信"是腾讯公司的注册商标。本工具与腾讯公司无任何关联。</p>

<p style="margin-top:20px;"><b>点击"我同意"即表示您已阅读、理解并同意上述所有条款。</b></p>
"""


class DisclaimerDialog(QDialog):
    """免责声明对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("disclaimerDialog")
        self.setWindowTitle("免责声明")
        self.setMinimumSize(520, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._accepted = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题图标
        title = QLabel("⚠ 重要提示")
        title.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 免责声明内容
        text_browser = QTextBrowser()
        text_browser.setObjectName("disclaimerText")
        text_browser.setHtml(DISCLAIMER_TEXT)
        text_browser.setOpenExternalLinks(True)
        layout.addWidget(text_browser)

        # 勾选框
        self._checkbox = QCheckBox("我已阅读并理解上述所有条款")
        self._checkbox.setFont(QFont("Microsoft YaHei UI", 11))
        self._checkbox.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self._checkbox)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._decline_btn = QPushButton("不同意并退出")
        self._decline_btn.setObjectName("dangerBtn")
        self._decline_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._decline_btn)

        self._accept_btn = QPushButton("我同意")
        self._accept_btn.setEnabled(False)
        self._accept_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self._accept_btn)

        layout.addLayout(btn_layout)

    def _on_checkbox_toggled(self, checked):
        self._accept_btn.setEnabled(checked)

    def _on_accept(self):
        self._accepted = True
        self.accept()

    @property
    def is_accepted(self):
        return self._accepted
