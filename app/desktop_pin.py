from PySide6.QtWidgets import QWidget, QMenu, QApplication
from PySide6.QtGui import QAction, QPixmap, QPainter, QColor, QRegion
from PySide6.QtCore import Qt, Signal, QPoint, QRect

from app.card_model import CardInfo
from app.card_widget import CardRenderer
from app.export_utils import export_to_file, copy_to_clipboard, grab_widget


class PinnedCardWindow(QWidget):
    closed = Signal(object)

    def __init__(self, card: CardInfo, parent=None):
        super().__init__(parent)
        self.card = card
        self._drag_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        PIN_W, PIN_H = 440, 260
        self._renderer = CardRenderer(card, self)
        self._renderer.setFixedSize(PIN_W, PIN_H)
        self.setFixedSize(PIN_W, PIN_H)

    def paintEvent(self, event):
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            from app.card_zoom import CardZoomDialog
            dlg = CardZoomDialog(self.card)
            dlg.exec()
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2d2d2d; color: white; border: 1px solid #555; padding: 4px; border-radius: 6px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #4fc3f7; color: black; }
            QMenu::separator { background: #555; height: 1px; margin: 4px 8px; }
        """)

        copy_act = QAction("复制卡片信息", self)
        copy_act.triggered.connect(self._copy_info)
        menu.addAction(copy_act)

        copy_img = QAction("复制为图片", self)
        copy_img.triggered.connect(self._copy_image)
        menu.addAction(copy_img)

        export_act = QAction("导出图片...", self)
        export_act.triggered.connect(self._export)
        menu.addAction(export_act)

        menu.addSeparator()

        close_act = QAction("关闭此钉图", self)
        close_act.triggered.connect(self.close)
        menu.addAction(close_act)

        menu.exec(event.globalPos())

    def closeEvent(self, event):
        self.closed.emit(self)
        super().closeEvent(event)

    def _copy_info(self):
        c = self.card
        text = f"{c.formatted_number}\n{c.expiry}\n{c.cvv}"
        QApplication.clipboard().setText(text)

    def _copy_image(self):
        copy_to_clipboard(grab_widget(self._renderer))

    def _export(self):
        pixmap = grab_widget(self._renderer)
        name = f"card_{self.card.number[-4:]}.png"
        export_to_file(pixmap, self, name)
