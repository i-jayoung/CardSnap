from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QFont, QGuiApplication


class Toast(QWidget):
    """Desktop toast notification that slides in from the bottom-right corner."""

    _instance = None

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        self._icon_label = QLabel()
        self._icon_label.setFixedWidth(20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(self._icon_label)

        self._text_label = QLabel()
        self._text_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self._text_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self._text_label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.95)
        self.setGraphicsEffect(self._opacity)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_anim.setDuration(300)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_anim.finished.connect(self._on_fade_done)

        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(300)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._bg_color = QColor(30, 30, 46, 230)
        self._fading_out = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(79, 195, 247, 120))
        p.setBrush(self._bg_color)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        p.end()

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = Toast()
        return cls._instance

    def show_message(self, text: str, icon: str = "⏳", duration_ms: int = 3000,
                     bg: str = None):
        self._hide_timer.stop()
        self._fade_anim.stop()
        self._slide_anim.stop()

        if bg == "success":
            self._bg_color = QColor(30, 60, 40, 230)
        elif bg == "error":
            self._bg_color = QColor(60, 30, 30, 230)
        elif bg == "warning":
            self._bg_color = QColor(60, 50, 20, 230)
        else:
            self._bg_color = QColor(30, 30, 46, 230)

        self._icon_label.setText(icon)
        self._text_label.setText(text)
        self.adjustSize()

        min_w = max(280, self._text_label.sizeHint().width() + 60)
        self.setFixedWidth(min(min_w, 420))

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        target_x = geo.right() - self.width() - 16
        target_y = geo.bottom() - self.height() - 16
        start_y = geo.bottom() + 10

        self._fading_out = False
        self._opacity.setOpacity(0.95)
        self.move(target_x, start_y)
        self.show()

        from PySide6.QtCore import QPoint
        self._slide_anim.setStartValue(QPoint(target_x, start_y))
        self._slide_anim.setEndValue(QPoint(target_x, target_y))
        self._slide_anim.start()

        if duration_ms > 0:
            self._hide_timer.start(duration_ms)

    def _fade_out(self):
        self._fading_out = True
        self._fade_anim.setStartValue(0.95)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_done(self):
        if not self._fading_out:
            return
        self._fading_out = False
        self.hide()
        self._opacity.setOpacity(0.95)

    def dismiss(self):
        self._hide_timer.stop()
        self._fade_out()
