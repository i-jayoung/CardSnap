from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPixmap, QGuiApplication, QCursor, QPen, QScreen
from PySide6.QtCore import Qt, Signal, QRect, QPoint


class ScreenCapture(QWidget):
    captured = Signal(QPixmap)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._origin = QPoint()
        self._current = QPoint()
        self._is_selecting = False
        self._screenshot: QPixmap | None = None

    def start(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.cancelled.emit()
            return

        geo = QRect()
        for s in QGuiApplication.screens():
            geo = geo.united(s.geometry())

        self._screenshot = screen.grabWindow(
            0, geo.x(), geo.y(), geo.width(), geo.height()
        )

        self.setGeometry(geo)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        if not self._screenshot:
            return

        p = QPainter(self)
        p.drawPixmap(0, 0, self._screenshot)

        overlay = QColor(0, 0, 0, 100)
        p.fillRect(self.rect(), overlay)

        if self._is_selecting:
            sel = QRect(self._origin, self._current).normalized()
            if not sel.isEmpty():
                p.setClipRect(sel)
                p.drawPixmap(0, 0, self._screenshot)
                p.setClipping(False)

                p.setPen(QPen(QColor("#4fc3f7"), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(sel)

                p.setPen(QColor(255, 255, 255, 200))
                from PySide6.QtGui import QFont
                p.setFont(QFont("Segoe UI", 9))
                size_text = f"{sel.width()} x {sel.height()}"
                p.drawText(sel.x(), sel.y() - 6, size_text)

        p.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._cancel()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            sel = QRect(self._origin, self._current).normalized()

            if sel.width() < 20 or sel.height() < 20:
                self._cancel()
                return

            self.hide()

            ratio = QGuiApplication.primaryScreen().devicePixelRatio()
            crop_rect = QRect(
                int(sel.x() * ratio),
                int(sel.y() * ratio),
                int(sel.width() * ratio),
                int(sel.height() * ratio),
            )
            cropped = self._screenshot.copy(crop_rect)
            self.captured.emit(cropped)
            self._cleanup()

    def _cancel(self):
        self.hide()
        self.cancelled.emit()
        self._cleanup()

    def _cleanup(self):
        self._is_selecting = False
        self._screenshot = None
