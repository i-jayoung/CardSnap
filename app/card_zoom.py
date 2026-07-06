import ctypes
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QApplication,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt

from app.card_model import CardInfo
from app.card_widget import CardRenderer
from app.export_utils import grab_widget, export_to_file, copy_to_clipboard


ZOOM_W = 600
ZOOM_H = 352


class CardZoomDialog(QDialog):
    """Enlarged card preview dialog triggered by clicking a card."""

    def __init__(self, card: CardInfo, parent=None):
        super().__init__(parent)
        self.card = card
        self.setWindowTitle(f"{card.brand_name} *{card.number[-4:]}")
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedSize(ZOOM_W + 40, ZOOM_H + 80)
        self._setup_ui()
        self._apply_dark_titlebar()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        self._renderer = CardRenderer(self.card)
        self._renderer.setFixedSize(ZOOM_W, ZOOM_H)
        layout.addWidget(self._renderer, 0, Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        copy_info_btn = QPushButton("📋 复制卡片信息")
        copy_info_btn.setFixedHeight(32)
        copy_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_info_btn.clicked.connect(self._copy_info)
        btn_row.addWidget(copy_info_btn)

        copy_img_btn = QPushButton("🖼 复制为图片")
        copy_img_btn.setFixedHeight(32)
        copy_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_img_btn.clicked.connect(self._copy_image)
        btn_row.addWidget(copy_img_btn)

        export_btn = QPushButton("💾 导出图片")
        export_btn.setFixedHeight(32)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QPushButton {
                background-color: #45475a; color: #cdd6f4;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 6px 16px; font-size: 12px;
            }
            QPushButton:hover { background-color: #585b70; border-color: #4fc3f7; }
            QPushButton:pressed { background-color: #4fc3f7; color: #1e1e2e; }
        """)

    def _copy_info(self):
        c = self.card
        QApplication.clipboard().setText(f"{c.formatted_number}\n{c.expiry}\n{c.cvv}")

    def _copy_image(self):
        copy_to_clipboard(grab_widget(self._renderer))

    def _export(self):
        pixmap = grab_widget(self._renderer)
        name = f"card_{self.card.number[-4:]}.png"
        export_to_file(pixmap, self, name)

    def _apply_dark_titlebar(self):
        try:
            hwnd = int(self.winId())
            val = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
            cap = ctypes.c_uint32(0x002E1E1E)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), ctypes.sizeof(cap))
            txt = ctypes.c_uint32(0x00F4D6CD)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(txt), ctypes.sizeof(txt))
        except Exception:
            pass
