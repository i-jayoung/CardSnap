from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
import numpy as np
from PIL import Image


class OcrWorker(QObject):
    """Runs OCR + card parsing in a background thread."""
    finished = Signal(str, list)  # (raw_text, parsed_cards)
    error = Signal(str)

    def __init__(self, qimage: QImage = None, text: str = None):
        super().__init__()
        self._raw_bytes = None
        self._width = 0
        self._height = 0
        self._bytes_per_line = 0
        self._text = text

        if qimage is not None and not qimage.isNull():
            fmt = qimage.convertToFormat(QImage.Format.Format_RGB888)
            self._width = fmt.width()
            self._height = fmt.height()
            self._bytes_per_line = fmt.bytesPerLine()
            ptr = fmt.bits()
            self._raw_bytes = bytes(np.frombuffer(ptr, dtype=np.uint8))

    def run(self):
        try:
            if self._raw_bytes is not None:
                arr = np.frombuffer(self._raw_bytes, dtype=np.uint8)
                arr = arr.reshape((self._height, self._bytes_per_line))
                arr = arr[:, :self._width * 3].reshape((self._height, self._width, 3))
                pil_img = Image.fromarray(arr)

                from app.ocr_engine import ocr_from_pil
                text = ocr_from_pil(pil_img)
            elif self._text is not None:
                text = self._text
            else:
                self.finished.emit("", [])
                return

            from app.card_parser import parse_text
            cards = parse_text(text) if text.strip() else []
            self.finished.emit(text, cards)
        except Exception as e:
            self.error.emit(str(e))
