import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QAction, QPixmap
from PySide6.QtCore import Signal, Qt

from app.autostart import is_autostart_enabled, set_autostart


def get_app_icon() -> QIcon:
    base = os.path.join(os.path.dirname(__file__), "resources", "icons")
    svg_path = os.path.join(base, "app_icon.svg")
    if os.path.exists(svg_path):
        return QIcon(svg_path)
    png_path = os.path.join(base, "app_icon.png")
    if os.path.exists(png_path):
        return QIcon(png_path)
    return QIcon()


class TrayIcon(QSystemTrayIcon):
    show_main_requested = Signal()
    screenshot_requested = Signal()
    clipboard_requested = Signal()
    close_all_pins_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, pin_manager, parent=None):
        super().__init__(parent)
        self._pin_manager = pin_manager
        self.setIcon(get_app_icon())
        self.setToolTip("CardSnap - 信用卡桌面助手")

        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background: #2d2d2d; color: white; border: 1px solid #555; padding: 4px; }
            QMenu::item:selected { background: #4fc3f7; color: black; }
            QMenu::separator { background: #555; height: 1px; margin: 4px 8px; }
        """)

        screenshot_act = QAction("截图识别 (Ctrl+Alt+C)", self)
        screenshot_act.triggered.connect(self.screenshot_requested.emit)
        menu.addAction(screenshot_act)

        clipboard_act = QAction("剪贴板识别 (Ctrl+Alt+V)", self)
        clipboard_act.triggered.connect(self.clipboard_requested.emit)
        menu.addAction(clipboard_act)

        menu.addSeparator()

        show_act = QAction("打开主界面", self)
        show_act.triggered.connect(self.show_main_requested.emit)
        menu.addAction(show_act)

        self._pins_menu = QMenu("管理钉图")
        self._pins_menu.setStyleSheet(menu.styleSheet())
        menu.addMenu(self._pins_menu)

        menu.addSeparator()

        self._autostart_act = QAction("开机自启动", self)
        self._autostart_act.setCheckable(True)
        self._autostart_act.setChecked(is_autostart_enabled())
        self._autostart_act.triggered.connect(self._toggle_autostart)
        menu.addAction(self._autostart_act)

        settings_act = QAction("设置...", self)
        settings_act.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_act)

        menu.addSeparator()

        quit_act = QAction("退出程序", self)
        quit_act.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_act)

        self.setContextMenu(menu)

    def update_pins_menu(self):
        self._pins_menu.clear()
        cards = self._pin_manager.cards
        count = self._pin_manager.count

        self._pins_menu.setTitle(f"管理钉图 (当前 {count} 张)")

        if count == 0:
            no_pins = QAction("无钉图", self)
            no_pins.setEnabled(False)
            self._pins_menu.addAction(no_pins)
        else:
            for card in cards:
                label = f"{card.brand_name} *{card.number[-4:]} - {card.expiry}"
                act = QAction(label, self)
                act.setEnabled(False)
                self._pins_menu.addAction(act)

            self._pins_menu.addSeparator()
            close_all = QAction("关闭所有钉图", self)
            close_all.triggered.connect(self.close_all_pins_requested.emit)
            self._pins_menu.addAction(close_all)

    def _toggle_autostart(self, checked):
        set_autostart(checked)
        self._autostart_act.setChecked(is_autostart_enabled())

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_requested.emit()
