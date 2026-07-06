from pynput import keyboard
from PySide6.QtCore import QObject, Signal


_QT_TO_PYNPUT = {
    "Ctrl": "<ctrl>",
    "Alt": "<alt>",
    "Shift": "<shift>",
    "Meta": "<cmd>",
}


def _qt_sequence_to_pynput(seq: str) -> str:
    parts = [p.strip() for p in seq.replace("+", " ").split()]
    result = []
    for p in parts:
        if p in _QT_TO_PYNPUT:
            result.append(_QT_TO_PYNPUT[p])
        else:
            result.append(p.lower())
    return "+".join(result)


class HotkeyManager(QObject):
    screenshot_triggered = Signal()
    clipboard_triggered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._listener: keyboard.GlobalHotKeys | None = None
        self._screenshot_key = "<ctrl>+<alt>+c"
        self._clipboard_key = "<ctrl>+<alt>+v"

    def start(self):
        if self._listener:
            return

        hotkeys = {
            self._screenshot_key: self._on_screenshot,
            self._clipboard_key: self._on_clipboard,
        }
        self._listener = keyboard.GlobalHotKeys(hotkeys)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def update_hotkeys(self, screenshot_seq: str, clipboard_seq: str):
        self._screenshot_key = _qt_sequence_to_pynput(screenshot_seq)
        self._clipboard_key = _qt_sequence_to_pynput(clipboard_seq)
        self.stop()
        self.start()

    def _on_screenshot(self):
        self.screenshot_triggered.emit()

    def _on_clipboard(self):
        self.clipboard_triggered.emit()
