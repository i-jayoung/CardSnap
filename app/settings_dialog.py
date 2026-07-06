import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QGroupBox, QFormLayout,
    QKeySequenceEdit, QMessageBox, QFileDialog,
)
from PySide6.QtGui import QKeySequence
from PySide6.QtCore import Qt, Signal

from app.storage import (
    load_settings, save_settings,
    export_backup, import_backup,
)
from app.autostart import is_autostart_enabled, set_autostart


class SettingsDialog(QDialog):
    settings_changed = Signal(dict)
    backup_imported = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(420, 480)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._settings = load_settings()
        self._setup_ui()
        self._apply_style()
        self._apply_dark_titlebar()

    def _apply_style(self):
        icon_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
        icon_dir = icon_dir.replace("\\", "/")
        self.setStyleSheet(f"""
            QDialog {{ background-color: #1e1e2e; }}
            QLabel {{ color: #cdd6f4; }}
            QPushButton {{
                background-color: #45475a; color: #cdd6f4;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: #585b70; border-color: #4fc3f7; }}
            QPushButton#primaryBtn {{
                background-color: #4fc3f7; color: #1e1e2e; font-weight: bold; border: none;
            }}
            QPushButton#primaryBtn:hover {{ background-color: #81d4fa; }}
            QCheckBox {{ color: #cdd6f4; spacing: 6px; }}
            QCheckBox::indicator {{ width: 20px; height: 20px; border: none; background: none; }}
            QCheckBox::indicator:unchecked {{ image: url({icon_dir}/checkbox-unchecked.svg); }}
            QCheckBox::indicator:checked {{ image: url({icon_dir}/checkbox-checked.svg); }}
        """)

    def _apply_dark_titlebar(self):
        try:
            import ctypes
            hwnd = int(self.winId())
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
            )
            caption = ctypes.c_uint32(0x002E1E1E)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 35, ctypes.byref(caption), ctypes.sizeof(caption)
            )
            text_c = ctypes.c_uint32(0x00F4D6CD)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 36, ctypes.byref(text_c), ctypes.sizeof(text_c)
            )
        except Exception:
            pass

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- hotkeys ---
        hk_group = QGroupBox("快捷键设置")
        hk_group.setStyleSheet("""
            QGroupBox {
                color: #cdd6f4; font-weight: bold; font-size: 13px;
                border: 1px solid #45475a; border-radius: 8px;
                margin-top: 12px; padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 12px; padding: 0 6px;
            }
        """)
        hk_form = QFormLayout()
        hk_form.setSpacing(10)

        self._screenshot_edit = QKeySequenceEdit(
            QKeySequence(self._settings["hotkey_screenshot"])
        )
        self._screenshot_edit.setFixedHeight(32)
        self._screenshot_edit.setStyleSheet(
            "background: #313244; color: #cdd6f4; border: 1px solid #45475a; "
            "border-radius: 6px; padding: 4px 8px;"
        )
        hk_form.addRow(self._make_label("截图识别："), self._screenshot_edit)

        self._clipboard_edit = QKeySequenceEdit(
            QKeySequence(self._settings["hotkey_clipboard"])
        )
        self._clipboard_edit.setFixedHeight(32)
        self._clipboard_edit.setStyleSheet(self._screenshot_edit.styleSheet())
        hk_form.addRow(self._make_label("剪贴板识别："), self._clipboard_edit)

        hk_group.setLayout(hk_form)
        layout.addWidget(hk_group)

        # --- general ---
        gen_group = QGroupBox("通用设置")
        gen_group.setStyleSheet(hk_group.styleSheet())
        gen_layout = QVBoxLayout()
        gen_layout.setSpacing(8)

        self._autostart_cb = QCheckBox("开机自启动（启动后自动最小化到托盘）")
        self._autostart_cb.setChecked(is_autostart_enabled())
        gen_layout.addWidget(self._autostart_cb)

        self._auto_pin_cb = QCheckBox("识别后自动钉到桌面")
        self._auto_pin_cb.setChecked(self._settings.get("auto_pin_on_recognize", True))
        gen_layout.addWidget(self._auto_pin_cb)

        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)

        # --- backup ---
        bk_group = QGroupBox("数据备份")
        bk_group.setStyleSheet(hk_group.styleSheet())
        bk_layout = QHBoxLayout()
        bk_layout.setSpacing(10)

        export_btn = QPushButton("📤 导出备份")
        export_btn.setFixedHeight(32)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_backup)
        bk_layout.addWidget(export_btn)

        import_btn = QPushButton("📥 导入备份")
        import_btn.setFixedHeight(32)
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(self._import_backup)
        bk_layout.addWidget(import_btn)

        bk_group.setLayout(bk_layout)
        layout.addWidget(bk_group)

        layout.addStretch()

        # --- buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedSize(90, 34)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #a6adc8; font-size: 12px; font-weight: normal;")
        return lbl

    def _save(self):
        screenshot_seq = self._screenshot_edit.keySequence().toString()
        clipboard_seq = self._clipboard_edit.keySequence().toString()

        if not screenshot_seq or not clipboard_seq:
            QMessageBox.warning(self, "提示", "快捷键不能为空")
            return

        set_autostart(self._autostart_cb.isChecked())

        new_settings = {
            "hotkey_screenshot": screenshot_seq,
            "hotkey_clipboard": clipboard_seq,
            "autostart": self._autostart_cb.isChecked(),
            "auto_pin_on_recognize": self._auto_pin_cb.isChecked(),
        }
        save_settings(new_settings)
        self.settings_changed.emit(new_settings)
        self.accept()

    def _export_backup(self):
        from app.storage import load_cards
        path, _ = QFileDialog.getSaveFileName(
            self, "导出备份", "CardSnap_Backup.json",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            cards = load_cards()
            export_backup(path, cards)
            QMessageBox.information(
                self, "导出成功",
                f"已导出 {len(cards)} 张卡片和所有设置到:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入备份", "",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if not path:
            return
        try:
            data = import_backup(path)
            card_count = len(data.get("cards", []))
            has_settings = data.get("settings") is not None

            parts = []
            if card_count:
                parts.append(f"{card_count} 张卡片")
            if has_settings:
                parts.append("设置")

            msg = QMessageBox(self)
            msg.setWindowTitle("确认导入")
            msg.setText(f"备份中包含: {', '.join(parts)}")
            msg.setInformativeText("导入后将与现有数据合并，是否继续？")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg.button(QMessageBox.StandardButton.Yes).setText("确认导入")
            msg.button(QMessageBox.StandardButton.No).setText("取消")
            if msg.exec() != QMessageBox.StandardButton.Yes:
                return

            if has_settings and data["settings"]:
                save_settings(data["settings"])
                self._settings = load_settings()
                self._screenshot_edit.setKeySequence(
                    QKeySequence(self._settings["hotkey_screenshot"])
                )
                self._clipboard_edit.setKeySequence(
                    QKeySequence(self._settings["hotkey_clipboard"])
                )
                self._autostart_cb.setChecked(
                    self._settings.get("autostart", False)
                )
                self._auto_pin_cb.setChecked(
                    self._settings.get("auto_pin_on_recognize", True)
                )

            self.backup_imported.emit(data)

            QMessageBox.information(
                self, "导入成功",
                f"已导入 {card_count} 张卡片" +
                ("和设置" if has_settings else "")
            )
        except ValueError as e:
            QMessageBox.warning(self, "导入失败", str(e))
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"文件格式错误:\n{e}")
