import os
from typing import List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QPlainTextEdit, QLabel, QScrollArea, QLineEdit,
    QApplication, QSystemTrayIcon, QSizePolicy, QMessageBox,
)
from PySide6.QtGui import QImage, QPixmap, QCloseEvent, QColor, QPalette, QIcon
from PySide6.QtCore import Qt, Slot, QTimer, QSize, QThread

from app.card_model import CardInfo
from app.card_parser import parse_text, detect_masked_cards
from app.card_widget import CardTile
from app.ocr_worker import OcrWorker
from app.screen_capture import ScreenCapture
from app.hotkey_manager import HotkeyManager
from app.tray_icon import TrayIcon, get_app_icon
from app.desktop_pin import PinnedCardWindow
from app.pin_manager import PinManager, PinSelectionDialog
from app.export_utils import grab_widget, export_to_file, copy_to_clipboard, batch_export
from app.storage import save_cards, load_cards, load_settings
from app.settings_dialog import SettingsDialog
from app.toast import Toast


class MainWindow(QMainWindow):
    def __init__(self, start_minimized: bool = False):
        super().__init__()
        self.setWindowTitle("CardSnap - 信用卡桌面助手")
        self.setMinimumSize(900, 620)
        self.resize(1080, 800)
        self.setWindowIcon(get_app_icon())

        self._cards: List[CardInfo] = []
        self._tiles: List[CardTile] = []
        self._really_quit = False
        self._start_minimized = start_minimized
        self._dark_titlebar_done = False
        self._ocr_thread: QThread | None = None
        self._ocr_source: str = ""
        self._ocr_generation: int = 0

        self._settings = load_settings()

        self._pin_manager = PinManager()
        self._pin_manager.set_on_change(self._on_pins_changed)
        self._screen_capture = ScreenCapture()
        self._screen_capture.captured.connect(self._on_screenshot_captured)
        self._hotkey_manager = HotkeyManager(self)
        self._hotkey_manager.update_hotkeys(
            self._settings["hotkey_screenshot"],
            self._settings["hotkey_clipboard"],
        )
        self._tray = TrayIcon(self._pin_manager, self)
        self._tray.update_hotkey_labels(
            self._settings["hotkey_screenshot"],
            self._settings["hotkey_clipboard"],
        )

        self._connect_signals()
        self._setup_ui()
        self._load_styles()

        self._tray.show()

        if not start_minimized:
            QTimer.singleShot(0, self._deferred_first_show)
        else:
            self._load_saved_cards()

    def _load_saved_cards(self):
        saved = load_cards()
        if saved:
            self._add_cards(saved, persist=False)

    def _deferred_first_show(self):
        self.setWindowOpacity(0)
        self.show()
        self._ensure_dark_titlebar()
        QTimer.singleShot(80, self._finish_first_show)

    def _finish_first_show(self):
        self.setWindowOpacity(1)
        QTimer.singleShot(0, self._load_saved_cards)

    def _ensure_dark_titlebar(self):
        if self._dark_titlebar_done:
            return
        self._dark_titlebar_done = True
        try:
            import ctypes
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value), ctypes.sizeof(value)
            )
            DWMWA_CAPTION_COLOR = 35
            caption_color = ctypes.c_uint32(0x002E1E1E)  # BGR: #1E1E2E
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_CAPTION_COLOR,
                ctypes.byref(caption_color), ctypes.sizeof(caption_color)
            )
            DWMWA_TEXT_COLOR = 36
            text_color = ctypes.c_uint32(0x00F4D6CD)  # BGR: #CDD6F4
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_TEXT_COLOR,
                ctypes.byref(text_color), ctypes.sizeof(text_color)
            )
        except Exception:
            pass

    @staticmethod
    def _apply_dark_titlebar_to(widget):
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

    def _connect_signals(self):
        self._hotkey_manager.screenshot_triggered.connect(
            self._start_screenshot, Qt.ConnectionType.QueuedConnection
        )
        self._hotkey_manager.clipboard_triggered.connect(
            self._paste_from_clipboard, Qt.ConnectionType.QueuedConnection
        )
        self._tray.show_main_requested.connect(self._show_main)
        self._tray.screenshot_requested.connect(self._start_screenshot)
        self._tray.clipboard_requested.connect(self._paste_from_clipboard)
        self._tray.close_all_pins_requested.connect(self._close_all_pins)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.quit_requested.connect(self._real_quit)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        hk1 = self._settings["hotkey_screenshot"]
        hk2 = self._settings["hotkey_clipboard"]

        self._screenshot_btn = QPushButton(f"📷 截图识别  {hk1}")
        self._screenshot_btn.setObjectName("primaryBtn")
        self._screenshot_btn.setFixedHeight(36)
        self._screenshot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._screenshot_btn.clicked.connect(self._start_screenshot)
        toolbar.addWidget(self._screenshot_btn)

        self._paste_btn = QPushButton(f"📋 剪贴板识别  {hk2}")
        self._paste_btn.setFixedHeight(36)
        self._paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._paste_btn.clicked.connect(self._paste_from_clipboard)
        toolbar.addWidget(self._paste_btn)

        toolbar.addStretch()

        gear_svg = os.path.join(os.path.dirname(__file__), "resources", "icons", "gear.svg")
        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon(gear_svg))
        settings_btn.setIconSize(QSize(20, 20))
        settings_btn.setFixedSize(36, 36)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("设置")
        settings_btn.setStyleSheet("""
            QPushButton {
                border-radius: 18px;
                background: #313244; border: 1px solid #45475a;
                padding: 6px;
            }
            QPushButton:hover { background: #45475a; border-color: #4fc3f7; }
        """)
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(settings_btn)

        main_layout.addLayout(toolbar)

        input_label = QLabel("输入信用卡信息（支持各种格式，每行一张卡）：")
        input_label.setStyleSheet("font-size: 12px; color: #a6adc8;")
        main_layout.addWidget(input_label)

        self._input_edit = QPlainTextEdit()
        self._input_edit.setPlaceholderText(
            "示例格式：\n"
            "4111111111111111 12/25 123\n"
            "5200 8282 8282 8210 | 06/26 | 456\n"
            "卡号:378282246310005 有效期:03/27 CVV:7890"
        )
        self._input_edit.setMaximumHeight(100)
        main_layout.addWidget(self._input_edit)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        parse_btn = QPushButton("✨ 识别并生成卡片")
        parse_btn.setObjectName("primaryBtn")
        parse_btn.setFixedHeight(34)
        parse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        parse_btn.clicked.connect(self._parse_input)
        action_bar.addWidget(parse_btn)

        action_bar.addStretch()

        pin_all_btn = QPushButton("📌 全部钉到桌面")
        pin_all_btn.setFixedHeight(34)
        pin_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_all_btn.clicked.connect(self._pin_all)
        action_bar.addWidget(pin_all_btn)

        main_layout.addLayout(action_bar)

        # --- search bar ---
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索卡片（卡号、后四位、品牌名称、有效期...）")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setFixedHeight(32)
        self._search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 6px;
                padding: 4px 12px; font-size: 12px;
            }
            QLineEdit:focus { border-color: #4fc3f7; }
        """)
        self._search_edit.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self._search_edit)

        # --- responsive card grid ---
        self._cards_container = QWidget()
        self._cards_container.setObjectName("cardsContainer")
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(6)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._cards_container)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self._scroll, 1)

        self._tile_min_width = 500
        self._grid_cols = 2

        # --- bottom bar ---
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        pin_sel_btn = QPushButton("📌 钉选中的")
        pin_sel_btn.setFixedHeight(30)
        pin_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pin_sel_btn.clicked.connect(self._pin_selected)
        bottom.addWidget(pin_sel_btn)

        export_sel_btn = QPushButton("💾 导出选中")
        export_sel_btn.setFixedHeight(30)
        export_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_sel_btn.clicked.connect(self._export_selected)
        bottom.addWidget(export_sel_btn)

        bottom.addStretch()

        self._total_label = QLabel("共 0 张")
        self._total_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        bottom.addWidget(self._total_label)

        self._selection_label = QLabel("已选 0 张")
        self._selection_label.setStyleSheet("color: #a6adc8; font-size: 12px; margin-left: 4px;")
        bottom.addWidget(self._selection_label)

        select_all_btn = QPushButton("全选")
        select_all_btn.setFixedHeight(30)
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        bottom.addWidget(select_all_btn)

        deselect_btn = QPushButton("取消全选")
        deselect_btn.setFixedHeight(30)
        deselect_btn.clicked.connect(lambda: self._set_all_checked(False))
        bottom.addWidget(deselect_btn)

        del_sel_btn = QPushButton("🗑 清空选中")
        del_sel_btn.setFixedHeight(30)
        del_sel_btn.setObjectName("dangerBtn")
        del_sel_btn.clicked.connect(self._delete_selected)
        bottom.addWidget(del_sel_btn)

        clear_btn = QPushButton("🗑 清空全部")
        clear_btn.setFixedHeight(30)
        clear_btn.setObjectName("dangerBtn")
        clear_btn.clicked.connect(self._clear_cards)
        bottom.addWidget(clear_btn)

        main_layout.addLayout(bottom)

        status_row = QHBoxLayout()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #a6adc8; font-size: 11px;")
        status_row.addWidget(self._status)
        status_row.addStretch()
        author = QLabel("JAYOUNG")
        author.setStyleSheet("color: #585b70; font-size: 10px; font-style: italic;")
        status_row.addWidget(author)
        main_layout.addLayout(status_row)

    def _load_styles(self):
        qss_path = os.path.join(os.path.dirname(__file__), "resources", "styles.qss")
        icon_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
        icon_dir = icon_dir.replace("\\", "/")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                qss = f.read().replace("ICON_DIR", icon_dir)
                self.setStyleSheet(qss)

    # ---------- card management ----------

    def _add_cards(self, cards: List[CardInfo], persist: bool = True):
        existing_numbers = {c.number for c in self._cards}
        added = 0
        skipped = 0
        self._cards_container.setUpdatesEnabled(False)
        for card in cards:
            if card.number in existing_numbers:
                skipped += 1
                continue
            existing_numbers.add(card.number)
            tile = CardTile(card, parent=self._cards_container)
            tile.pin_requested.connect(self._pin_single)
            tile.export_requested.connect(self._export_single)
            tile.delete_requested.connect(self._delete_tile)
            tile.checkbox.stateChanged.connect(self._update_selection_count)
            self._tiles.append(tile)
            self._cards.append(card)
            added += 1

        self._rebuild_grid()
        self._cards_container.setUpdatesEnabled(True)
        self._update_status()
        if persist:
            self._persist()

        if skipped > 0:
            self._status.setText(
                f"成功添加 {added} 张卡片，{skipped} 张重复已跳过"
            )
        return added

    def _delete_tile(self, tile: CardTile):
        msg = QMessageBox(self)
        msg.setWindowTitle("确认删除")
        msg.setText(f"确定要删除卡片 **** {tile.card.number[-4:]} 吗？")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("确认删除")
        msg.button(QMessageBox.StandardButton.No).setText("取消")
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
            QPushButton {
                background-color: #45475a; color: #cdd6f4;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 6px 20px; min-width: 80px;
            }
            QPushButton:hover { background-color: #585b70; border-color: #4fc3f7; }
        """)
        self._apply_dark_titlebar_to(msg)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        if tile in self._tiles:
            self._tiles.remove(tile)
        if tile.card in self._cards:
            self._pin_manager.close_card(tile.card)
            self._tray.update_pins_menu()
            self._cards.remove(tile.card)
        tile.deleteLater()
        self._rebuild_grid()
        self._update_status()
        self._persist()

    def _delete_selected(self):
        selected = [t for t in self._tiles if t.checkbox.isChecked()]
        if not selected:
            self._status.setText("没有选中任何卡片")
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("确认删除")
        msg.setText(f"确定要删除选中的 {len(selected)} 张卡片吗？")
        msg.setInformativeText("此操作无法撤销。")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("确认删除")
        msg.button(QMessageBox.StandardButton.No).setText("取消")
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
            QPushButton {
                background-color: #45475a; color: #cdd6f4;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 6px 20px; min-width: 80px;
            }
            QPushButton:hover { background-color: #585b70; border-color: #4fc3f7; }
        """)
        self._apply_dark_titlebar_to(msg)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        for tile in selected:
            if tile.card in self._cards:
                self._pin_manager.close_card(tile.card)
                self._cards.remove(tile.card)
            self._tiles.remove(tile)
            tile.deleteLater()
        self._tray.update_pins_menu()
        self._rebuild_grid()
        self._update_status()
        self._persist()
        self._status.setText(f"已删除 {len(selected)} 张卡片")

    def _clear_cards(self):
        if not self._cards:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("确认清空")
        msg.setText(f"确定要清空全部 {len(self._cards)} 张卡片吗？")
        msg.setInformativeText("此操作无法撤销。")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("确认清空")
        msg.button(QMessageBox.StandardButton.No).setText("取消")
        msg.setStyleSheet("""
            QMessageBox { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; }
            QPushButton {
                background-color: #45475a; color: #cdd6f4;
                border: 1px solid #585b70; border-radius: 6px;
                padding: 6px 20px; min-width: 80px;
            }
            QPushButton:hover { background-color: #585b70; border-color: #4fc3f7; }
        """)
        self._apply_dark_titlebar_to(msg)
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        self._pin_manager.close_all()
        self._tray.update_pins_menu()
        for tile in self._tiles:
            tile.deleteLater()
        self._tiles.clear()
        self._cards.clear()
        self._rebuild_grid()
        self._update_status()
        self._persist()

    def _calc_grid_cols(self) -> int:
        if not hasattr(self, '_scroll'):
            return 2
        vp_width = self._scroll.viewport().width()
        spacing = self._cards_layout.spacing()
        cols = max(1, (vp_width + spacing) // (self._tile_min_width + spacing))
        return cols

    def _rebuild_grid(self):
        while self._cards_layout.count():
            self._cards_layout.takeAt(0)

        cols = self._calc_grid_cols()
        self._grid_cols = cols

        query = self._search_edit.text().strip().lower() if hasattr(self, '_search_edit') else ""
        visible_idx = 0
        for tile in self._tiles:
            if query and not self._tile_matches(tile, query):
                tile.setVisible(False)
            else:
                tile.setVisible(True)
                row = visible_idx // cols
                col = visible_idx % cols
                self._cards_layout.addWidget(tile, row, col)
                visible_idx += 1

        if hasattr(self, '_search_edit') and query:
            self._search_edit.setToolTip(f"匹配 {visible_idx}/{len(self._tiles)}")
        elif hasattr(self, '_search_edit'):
            self._search_edit.setToolTip("")

        if hasattr(self, '_selection_label'):
            self._update_selection_count()

    @staticmethod
    def _tile_matches(tile, query: str) -> bool:
        card = tile.card
        return (
            query in card.number
            or query in card.number[-4:]
            or query in card.brand_name.lower()
            or query in card.expiry
            or query in card.cvv
            or query in card.formatted_number.lower()
        )

    def _on_search_changed(self, text: str):
        self._rebuild_grid()

    def _persist(self):
        save_cards(self._cards)

    def _update_status(self):
        n = len(self._cards)
        self._status.setText(f"共 {n} 张卡片" if n else "")
        self._tray.update_pins_menu()
        if hasattr(self, '_selection_label'):
            self._update_selection_count()

    # ---------- input parsing ----------

    @Slot()
    def _parse_input(self):
        text = self._input_edit.toPlainText().strip()
        if not text:
            self._status.setText("请输入信用卡信息")
            return
        self._status.setText("正在解析输入...")
        self._start_ocr_task("手动输入", text=text)


    # ---------- async OCR ----------

    def _start_ocr_task(self, source: str, qimage: QImage = None, text: str = None):
        self._cleanup_ocr_thread()
        self._ocr_source = source
        self._ocr_generation += 1

        if qimage is not None:
            Toast.get().show_message(f"正在识别{source}...", icon="🔍", duration_ms=0)
        else:
            Toast.get().show_message("正在解析卡片信息...", icon="⏳", duration_ms=0)

        self._ocr_thread = QThread()
        self._ocr_worker = OcrWorker(qimage=qimage, text=text)
        self._ocr_worker._generation = self._ocr_generation
        self._ocr_worker.moveToThread(self._ocr_thread)
        self._ocr_thread.started.connect(self._ocr_worker.run)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_thread.start()

    def _cleanup_ocr_thread(self):
        if self._ocr_thread is not None:
            if self._ocr_worker is not None:
                self._ocr_worker.finished.disconnect()
                self._ocr_worker.error.disconnect()
            self._ocr_thread.quit()
            self._ocr_thread.wait(5000)
            if self._ocr_worker is not None:
                self._ocr_worker.deleteLater()
            self._ocr_worker = None
            self._ocr_thread = None

    @Slot(str, list)
    def _on_ocr_finished(self, text: str, cards: list):
        worker = self.sender()
        if worker and hasattr(worker, '_generation') and worker._generation != self._ocr_generation:
            return
        source = self._ocr_source
        self._cleanup_ocr_thread()
        toast = Toast.get()

        if not text.strip():
            msg = f"{source}中未识别到文字"
            self._status.setText(msg)
            toast.show_message(msg, icon="⚠️", duration_ms=3000, bg="warning")
            return

        if cards:
            self._add_cards(cards)
            if source == "手动输入":
                self._input_edit.clear()
                masked = detect_masked_cards(text)
                msg = f"成功识别 {len(cards)} 张卡片"
                if masked:
                    msg += f"（检测到 {len(masked)} 个掩码卡号，请补全完整卡号）"
                self._status.setText(msg)
            else:
                self._auto_pin(cards, source)
            toast.show_message(
                f"从{source}识别到 {len(cards)} 张卡片",
                icon="✅", duration_ms=3000, bg="success",
            )
            return

        masked = detect_masked_cards(text)
        if source == "手动输入":
            hint = "未能识别到有效的信用卡信息，请检查格式"
            if masked:
                hint += f"（检测到 {len(masked)} 个掩码卡号，请补全完整卡号）"
        else:
            hint = f"{source}中未识别到卡片信息"
            if masked:
                hint += f"\n检测到 {len(masked)} 个掩码卡号，请补全完整卡号"
            hint += f"\n识别内容: {text[:200]}"
            self._input_edit.setPlainText(text)
        self._status.setText(hint)
        toast.show_message("未识别到卡片信息", icon="⚠️", duration_ms=3000, bg="warning")

    @Slot(str)
    def _on_ocr_error(self, err: str):
        worker = self.sender()
        if worker and hasattr(worker, '_generation') and worker._generation != self._ocr_generation:
            return
        self._cleanup_ocr_thread()
        self._status.setText(f"识别出错: {err}")
        Toast.get().show_message(f"识别出错: {err}", icon="❌", duration_ms=4000, bg="error")

    # ---------- screenshot ----------

    @Slot()
    def _start_screenshot(self):
        if self.isVisible() and not self.isMinimized():
            self.showMinimized()
        QTimer.singleShot(400, self._do_screenshot)

    def _do_screenshot(self):
        self._screen_capture.start()

    @Slot(QPixmap)
    def _on_screenshot_captured(self, pixmap: QPixmap):
        self._status.setText("正在 OCR 识别（后台处理中）...")
        self._start_ocr_task("截图", qimage=pixmap.toImage())

    @Slot(list)
    def _on_pin_selection(self, selected_cards):
        self._pin_manager.pin_cards(selected_cards)
        self._tray.update_pins_menu()
        self._status.setText(f"已钉 {len(selected_cards)} 张卡片到桌面")

    # ---------- clipboard ----------

    @Slot()
    def _paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()

        if mime.hasImage():
            qimage = clipboard.image()
            if not qimage.isNull():
                self._status.setText("正在识别剪贴板图片（后台处理中）...")
                self._start_ocr_task("剪贴板图片", qimage=qimage)
                return

        if mime.hasText():
            text = mime.text().strip()
            if text:
                self._status.setText("正在识别剪贴板文本...")
                self._start_ocr_task("剪贴板文本", text=text)
                return

        self._status.setText("剪贴板中没有可识别的内容")

    def _auto_pin(self, cards: List[CardInfo], source: str):
        auto_pin = self._settings.get("auto_pin_on_recognize", True)
        if not auto_pin:
            self._status.setText(f"从{source}识别到 {len(cards)} 张卡片")
            return

        if len(cards) == 1:
            self._pin_manager.pin_card(cards[0])
            self._tray.update_pins_menu()
            self._status.setText(f"从{source}识别到 1 张卡片，已钉到桌面")
        else:
            for card in cards:
                self._pin_manager.pin_card(card)
            self._tray.update_pins_menu()
            self._status.setText(f"从{source}识别到 {len(cards)} 张卡片，已全部钉到桌面")

    # ---------- pin / export ----------

    @Slot(CardInfo)
    def _pin_single(self, card: CardInfo):
        self._pin_manager.pin_card(card)
        self._tray.update_pins_menu()
        self._status.setText(f"已钉 {card.brand_name} *{card.number[-4:]} 到桌面")

    @Slot()
    def _pin_all(self):
        if not self._cards:
            return
        self._pin_manager.pin_cards(self._cards)
        self._tray.update_pins_menu()
        self._status.setText(f"已钉 {len(self._cards)} 张卡片到桌面")

    @Slot()
    def _pin_selected(self):
        selected = [t.card for t in self._tiles if t.is_checked]
        if not selected:
            self._status.setText("请先勾选要钉的卡片")
            return
        self._pin_manager.pin_cards(selected)
        self._tray.update_pins_menu()
        self._status.setText(f"已钉 {len(selected)} 张卡片到桌面")

    @Slot(CardInfo)
    def _export_single(self, card: CardInfo):
        for tile in self._tiles:
            if tile.card is card:
                pixmap = grab_widget(tile.renderer)
                name = f"card_{card.number[-4:]}.png"
                path = export_to_file(pixmap, self, name)
                if path:
                    self._status.setText(f"已导出到 {path}")
                return

    @Slot()
    def _export_selected(self):
        selected_tiles = [t for t in self._tiles if t.is_checked]
        if not selected_tiles:
            self._status.setText("请先勾选要导出的卡片")
            return
        pixmaps = [grab_widget(t.renderer) for t in selected_tiles]
        paths = batch_export(pixmaps, self)
        if paths:
            self._status.setText(f"已导出 {len(paths)} 张卡片")

    @Slot()
    def _close_all_pins(self):
        self._pin_manager.close_all()
        self._tray.update_pins_menu()
        self._status.setText("已关闭所有钉图")

    def _on_pins_changed(self):
        self._tray.update_pins_menu()

    def _set_all_checked(self, checked: bool):
        for tile in self._tiles:
            tile.checkbox.setChecked(checked)

    def _update_selection_count(self):
        visible = [t for t in self._tiles if t.isVisible()]
        selected = sum(1 for t in visible if t.is_checked)
        total = len(visible)
        self._total_label.setText(f"共 {total} 张")
        self._selection_label.setText(f"已选 {selected} 张")

    # ---------- settings ----------

    @Slot()
    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.backup_imported.connect(self._on_backup_imported)
        dlg.exec()

    @Slot(dict)
    def _on_backup_imported(self, data: dict):
        cards = data.get("cards", [])
        if cards:
            added = self._add_cards(cards)
            self._status.setText(f"从备份导入了 {added} 张新卡片")
        if data.get("settings"):
            self._on_settings_changed(data["settings"])

    @Slot(dict)
    def _on_settings_changed(self, new_settings: dict):
        self._settings = new_settings
        self._hotkey_manager.update_hotkeys(
            new_settings["hotkey_screenshot"],
            new_settings["hotkey_clipboard"],
        )
        hk1 = new_settings["hotkey_screenshot"]
        hk2 = new_settings["hotkey_clipboard"]
        self._screenshot_btn.setText(f"📷 截图识别  {hk1}")
        self._paste_btn.setText(f"📋 剪贴板识别  {hk2}")
        self._tray.update_hotkey_labels(hk1, hk2)
        self._status.setText("设置已保存")

    # ---------- window lifecycle ----------

    def _show_main(self):
        if not self._dark_titlebar_done:
            self.setWindowOpacity(0)
            self.showNormal()
            self._ensure_dark_titlebar()
            QTimer.singleShot(80, lambda: self.setWindowOpacity(1))
        else:
            self.showNormal()
        self.activateWindow()
        self.raise_()

    def _real_quit(self):
        self._really_quit = True
        self._hotkey_manager.stop()
        self._cleanup_ocr_thread()
        self._pin_manager.close_all()
        QApplication.quit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        new_cols = self._calc_grid_cols()
        if new_cols != self._grid_cols:
            self._rebuild_grid()

    def closeEvent(self, event: QCloseEvent):
        if self._really_quit:
            event.accept()
        else:
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "CardSnap",
                "应用已最小化到系统托盘，双击图标可重新打开",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
