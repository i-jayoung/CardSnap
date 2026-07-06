import os
from typing import List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QCheckBox,
    QPushButton, QLabel, QScrollArea, QWidget,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt, Signal

from app.card_model import CardInfo
from app.card_widget import CardRenderer
from app.desktop_pin import PinnedCardWindow


def _apply_dark_titlebar(widget):
    try:
        import ctypes
        hwnd = int(widget.winId())
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        cap = ctypes.c_uint32(0x002E1E1E)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), ctypes.sizeof(cap))
        txt = ctypes.c_uint32(0x00F4D6CD)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(txt), ctypes.sizeof(txt))
    except Exception:
        pass


def _load_dialog_style() -> str:
    icon_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
    icon_dir = icon_dir.replace("\\", "/")
    return f"""
        QDialog {{ background-color: #1e1e2e; }}
        QLabel {{ color: #cdd6f4; }}
        QPushButton {{
            background-color: #45475a; color: #cdd6f4;
            border: 1px solid #585b70; border-radius: 6px;
            padding: 6px 16px; font-size: 12px;
        }}
        QPushButton:hover {{ background-color: #585b70; border-color: #4fc3f7; }}
        QPushButton:pressed {{ background-color: #4fc3f7; color: #1e1e2e; }}
        QPushButton#primaryBtn {{
            background-color: #4fc3f7; color: #1e1e2e; font-weight: bold; border: none;
        }}
        QPushButton#primaryBtn:hover {{ background-color: #81d4fa; }}
        QCheckBox {{ color: #cdd6f4; spacing: 6px; }}
        QCheckBox::indicator {{ width: 20px; height: 20px; border: none; background: none; }}
        QCheckBox::indicator:unchecked {{ image: url({icon_dir}/checkbox-unchecked.svg); }}
        QCheckBox::indicator:checked {{ image: url({icon_dir}/checkbox-checked.svg); }}
        QScrollArea {{ border: none; background: transparent; }}
        QWidget#pinScrollContainer {{ background: transparent; }}
        QWidget#pinCardCell {{ background-color: #282838; border-radius: 8px; padding: 6px; }}
        QScrollBar:vertical {{
            background: #313244; width: 8px; border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: #585b70; border-radius: 4px; min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: #4fc3f7; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    """


class PinManager:
    """Manages all pinned card windows on the desktop."""

    def __init__(self):
        self._pins: list[PinnedCardWindow] = []
        self._on_change_callback = None

    def set_on_change(self, callback):
        self._on_change_callback = callback

    def _notify_change(self):
        if self._on_change_callback:
            self._on_change_callback()

    @property
    def count(self) -> int:
        return len(self._pins)

    @property
    def cards(self) -> list[CardInfo]:
        return [p.card for p in self._pins]

    def is_pinned(self, card: CardInfo) -> bool:
        return any(p.card.number == card.number for p in self._pins)

    def pin_card(self, card: CardInfo) -> PinnedCardWindow | None:
        if self.is_pinned(card):
            return None
        win = PinnedCardWindow(card)
        win.closed.connect(self._on_pin_closed)
        pos = self._next_position()
        win.move(pos)
        win.show()
        self._pins.append(win)
        return win

    def pin_cards(self, cards: List[CardInfo]):
        for card in cards:
            self.pin_card(card)

    def close_all(self):
        for pin in list(self._pins):
            pin.close()
        self._pins.clear()

    def close_card(self, card: CardInfo):
        for pin in list(self._pins):
            if pin.card.number == card.number:
                pin.close()
                break

    def _on_pin_closed(self, pin_window):
        if pin_window in self._pins:
            self._pins.remove(pin_window)
            self._notify_change()

    def _next_position(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return Qt.AlignmentFlag.AlignCenter

        geo = screen.availableGeometry()
        margin = 20
        card_w, card_h = 340, 200
        spacing = 16

        idx = len(self._pins)
        cols = max(1, (geo.height() - 2 * margin) // (card_h + spacing))
        col = idx // cols
        row = idx % cols

        x = geo.right() - card_w - margin - col * (card_w + spacing)
        y = geo.top() + margin + row * (card_h + spacing)

        from PySide6.QtCore import QPoint
        return QPoint(max(geo.left(), x), min(y, geo.bottom() - card_h))


class PinSelectionDialog(QDialog):
    """Dialog for selecting which cards to pin after batch recognition."""
    cards_selected = Signal(list)

    def __init__(self, cards: List[CardInfo], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择要钉到桌面的卡片")
        self.setMinimumWidth(920)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._cards = cards
        self._checkboxes: list[QCheckBox] = []
        self._setup_ui()
        self.setStyleSheet(_load_dialog_style())
        _apply_dark_titlebar(self)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"识别到 {len(self._cards)} 张卡片，请选择要钉到桌面的卡片：")
        header.setStyleSheet("font-size: 13px; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(520)
        container = QWidget()
        container.setObjectName("pinScrollContainer")
        grid = QGridLayout(container)
        grid.setSpacing(12)
        grid.setContentsMargins(6, 6, 6, 6)

        for i, card in enumerate(self._cards):
            cell = QHBoxLayout()
            cell.setSpacing(8)
            cell.setContentsMargins(8, 6, 8, 6)
            cb = QCheckBox()
            cb.setChecked(True)
            self._checkboxes.append(cb)

            preview = CardRenderer(card)
            preview.setFixedSize(PREVIEW_W, PREVIEW_H)

            cell.addWidget(cb, 0, Qt.AlignmentFlag.AlignVCenter)
            cell.addWidget(preview, 0, Qt.AlignmentFlag.AlignVCenter)

            wrapper = QWidget()
            wrapper.setObjectName("pinCardCell")
            wrapper.setLayout(cell)
            row = i // 2
            col = i % 2
            grid.addWidget(wrapper, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        select_all = QPushButton("全选")
        select_all.clicked.connect(lambda: self._set_all(True))
        btn_layout.addWidget(select_all)

        deselect_all = QPushButton("取消全选")
        deselect_all.clicked.connect(lambda: self._set_all(False))
        btn_layout.addWidget(deselect_all)

        btn_layout.addStretch()

        pin_selected = QPushButton("📌 钉选中的")
        pin_selected.setFixedHeight(32)
        pin_selected.clicked.connect(self._pin_selected)
        btn_layout.addWidget(pin_selected)

        pin_all = QPushButton("📌 全部钉图")
        pin_all.setObjectName("primaryBtn")
        pin_all.setFixedHeight(32)
        pin_all.clicked.connect(self._pin_all)
        btn_layout.addWidget(pin_all)

        cancel = QPushButton("取消")
        cancel.setFixedHeight(32)
        cancel.clicked.connect(self.reject)
        btn_layout.addWidget(cancel)

        layout.addLayout(btn_layout)

    def _set_all(self, checked: bool):
        for cb in self._checkboxes:
            cb.setChecked(checked)

    def _pin_selected(self):
        selected = [
            card for card, cb in zip(self._cards, self._checkboxes)
            if cb.isChecked()
        ]
        self.cards_selected.emit(selected)
        self.accept()

    def _pin_all(self):
        self.cards_selected.emit(list(self._cards))
        self.accept()


PREVIEW_W = 360
PREVIEW_H = 200
