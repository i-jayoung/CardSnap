from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QPushButton, QLabel, QSizePolicy, QApplication,
)
from PySide6.QtGui import (
    QPainter, QLinearGradient, QColor, QFont, QPen,
    QBrush, QPixmap,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer

from app.card_model import CardInfo
from app.qr_generator import qr_to_qpixmap


CARD_WIDTH = 340
CARD_HEIGHT = 200


class CardRenderer(QWidget):
    """Pure card visual — no buttons, used for both display and pinning."""
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, card: CardInfo, parent=None):
        super().__init__(parent)
        self.card = card
        self._qr_pixmap = None
        self._qr_ready = False
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self.clicked.emit)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._click_timer.isActive():
                self._click_timer.start()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_timer.stop()
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def _generate_qr(self):
        self._qr_pixmap = qr_to_qpixmap(self.card, size=120)

    def paintEvent(self, event):
        if not self._qr_ready:
            self._qr_ready = True
            self._qr_pixmap = qr_to_qpixmap(self.card, size=120)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        sx = self.width() / CARD_WIDTH
        sy = self.height() / CARD_HEIGHT
        p.scale(sx, sy)

        c1, c2 = self.card.brand_colors
        grad = QLinearGradient(0, 0, CARD_WIDTH, CARD_HEIGHT)
        grad.setColorAt(0, QColor(c1))
        grad.setColorAt(1, QColor(c2))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, CARD_WIDTH, CARD_HEIGHT, 14, 14)

        p.setOpacity(0.06)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(QPointF(CARD_WIDTH * 0.75, CARD_HEIGHT * 0.3), 120, 120)
        p.drawEllipse(QPointF(CARD_WIDTH * 0.85, CARD_HEIGHT * 0.7), 80, 80)
        p.setOpacity(1.0)

        self._draw_chip(p)
        self._draw_brand_name(p)
        self._draw_card_number(p)
        self._draw_expiry(p)
        self._draw_cvv(p)
        self._draw_qr(p)

        p.end()

    def _draw_chip(self, p: QPainter):
        chip_x, chip_y = 24, 40
        chip_w, chip_h = 40, 30
        p.setBrush(QColor("#d4af37"))
        p.setPen(QPen(QColor("#b8960c"), 1))
        p.drawRoundedRect(chip_x, chip_y, chip_w, chip_h, 4, 4)

        p.setPen(QPen(QColor("#b8960c"), 0.8))
        p.drawLine(chip_x + 14, chip_y, chip_x + 14, chip_y + chip_h)
        p.drawLine(chip_x + 27, chip_y, chip_x + 27, chip_y + chip_h)
        p.drawLine(chip_x, chip_y + 15, chip_x + chip_w, chip_y + 15)

    def _draw_brand_name(self, p: QPainter):
        p.setPen(QColor(255, 255, 255, 200))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(CARD_WIDTH - 150, 12, 140, 24),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   self.card.brand_name)

    def _draw_card_number(self, p: QPainter):
        p.setPen(QColor(255, 255, 255))
        font = QFont("Consolas", 16, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        p.setFont(font)
        p.drawText(QRectF(24, 88, CARD_WIDTH - 48, 30),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.card.formatted_number)

    def _draw_expiry(self, p: QPainter):
        p.setPen(QColor(255, 255, 255, 160))
        small = QFont("Segoe UI", 8)
        p.setFont(small)
        p.drawText(QRectF(24, 128, 80, 16),
                   Qt.AlignmentFlag.AlignLeft, "VALID THRU")

        val_font = QFont("Consolas", 13, QFont.Weight.Bold)
        p.setFont(val_font)
        if self.card.expiry:
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(24, 144, 80, 24),
                       Qt.AlignmentFlag.AlignLeft, self.card.expiry)
        else:
            p.setPen(QColor(255, 200, 200, 180))
            p.drawText(QRectF(24, 144, 80, 24),
                       Qt.AlignmentFlag.AlignLeft, "--/--")

    def _draw_cvv(self, p: QPainter):
        p.setPen(QColor(255, 255, 255, 160))
        small = QFont("Segoe UI", 8)
        p.setFont(small)
        p.drawText(QRectF(120, 128, 60, 16),
                   Qt.AlignmentFlag.AlignLeft, "CVV")

        val_font = QFont("Consolas", 13, QFont.Weight.Bold)
        p.setFont(val_font)
        if self.card.cvv:
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(120, 144, 60, 24),
                       Qt.AlignmentFlag.AlignLeft, self.card.cvv)
        else:
            p.setPen(QColor(255, 200, 200, 180))
            p.drawText(QRectF(120, 144, 60, 24),
                       Qt.AlignmentFlag.AlignLeft, "---")

    def _draw_qr(self, p: QPainter):
        if self._qr_pixmap and not self._qr_pixmap.isNull():
            qr_size = 72
            x = CARD_WIDTH - qr_size - 10
            y = CARD_HEIGHT - qr_size - 10
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255))
            p.drawRoundedRect(x - 3, y - 3, qr_size + 6, qr_size + 6, 4, 4)
            p.drawPixmap(x, y, qr_size, qr_size, self._qr_pixmap)


class CardTile(QWidget):
    """Horizontal card row: checkbox | card | action buttons. For vertical scroll list."""
    pin_requested = Signal(CardInfo)
    export_requested = Signal(CardInfo)
    delete_requested = Signal(object)  # emits self

    def __init__(self, card: CardInfo, parent=None):
        super().__init__(parent)
        self.card = card
        self.setFixedHeight(216)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.setFixedSize(22, 22)
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignVCenter)

        self.renderer = CardRenderer(self.card)
        self.renderer.clicked.connect(self._toggle_check)
        self.renderer.double_clicked.connect(self._show_zoom)
        layout.addWidget(self.renderer, 0, Qt.AlignmentFlag.AlignVCenter)

        info_btns = QVBoxLayout()
        info_btns.setSpacing(6)

        brand_label = QLabel(f"{self.card.brand_name}")
        brand_label.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: bold;")
        info_btns.addWidget(brand_label)

        num_label = QLabel(f"**** {self.card.number[-4:]}")
        num_label.setStyleSheet("color: #a6adc8; font-size: 12px; font-family: Consolas;")
        info_btns.addWidget(num_label)

        exp_label = QLabel(f"有效期 {self.card.expiry}")
        exp_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        info_btns.addWidget(exp_label)

        info_btns.addStretch()

        pin_btn = QPushButton("📌 钉到桌面")
        pin_btn.setFixedSize(110, 30)
        pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_btn.clicked.connect(lambda: self.pin_requested.emit(self.card))
        info_btns.addWidget(pin_btn)

        copy_btn = QPushButton("📋 复制信息")
        copy_btn.setFixedSize(110, 30)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_info)
        info_btns.addWidget(copy_btn)

        export_btn = QPushButton("💾 导出图片")
        export_btn.setFixedSize(110, 30)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(lambda: self.export_requested.emit(self.card))
        info_btns.addWidget(export_btn)

        del_btn = QPushButton("✕ 删除")
        del_btn.setFixedSize(110, 30)
        del_btn.setObjectName("dangerBtn")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        info_btns.addWidget(del_btn)

        layout.addLayout(info_btns)
        layout.addStretch()

    @property
    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def _toggle_check(self):
        self.checkbox.setChecked(not self.checkbox.isChecked())

    def _copy_info(self):
        c = self.card
        text = f"{c.formatted_number}\n{c.expiry}\n{c.cvv}"
        QApplication.clipboard().setText(text)

    def _show_zoom(self):
        from app.card_zoom import CardZoomDialog
        dlg = CardZoomDialog(self.card, self.window())
        dlg.exec()
