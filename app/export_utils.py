import os
from PySide6.QtWidgets import QWidget, QFileDialog, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QDir


def grab_widget(widget: QWidget) -> QPixmap:
    return widget.grab()


def export_to_file(pixmap: QPixmap, parent: QWidget = None, default_name: str = "card.png") -> str | None:
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "导出卡片图片",
        os.path.join(QDir.homePath(), "Desktop", default_name),
        "PNG (*.png);;JPEG (*.jpg *.jpeg);;All Files (*)",
    )
    if path:
        fmt = "JPEG" if path.lower().endswith((".jpg", ".jpeg")) else "PNG"
        pixmap.save(path, fmt)
        return path
    return None


def copy_to_clipboard(pixmap: QPixmap):
    clipboard = QApplication.clipboard()
    clipboard.setPixmap(pixmap)


def batch_export(pixmaps: list, parent: QWidget = None) -> list:
    directory = QFileDialog.getExistingDirectory(
        parent,
        "选择导出目录",
        QDir.homePath(),
    )
    if not directory:
        return []

    saved = []
    for i, pixmap in enumerate(pixmaps):
        path = os.path.join(directory, f"card_{i + 1:03d}.png")
        pixmap.save(path, "PNG")
        saved.append(path)
    return saved
