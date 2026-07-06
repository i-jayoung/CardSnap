import sys
import os

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QSharedMemory
from PySide6.QtGui import QFont


def main():
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app.setQuitOnLastWindowClosed(False)

    shared = QSharedMemory("CardSnap_SingleInstance")
    if not shared.create(1):
        QMessageBox.information(None, "CardSnap", "CardSnap 已在运行中。")
        sys.exit(0)

    font = QFont("Segoe UI", 10)
    font.setFamilies(["Segoe UI", "Microsoft YaHei", "sans-serif"])
    app.setFont(font)

    from app.tray_icon import get_app_icon
    app.setWindowIcon(get_app_icon())

    start_minimized = "--minimized" in sys.argv

    from app.main_window import MainWindow
    window = MainWindow(start_minimized=start_minimized)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
