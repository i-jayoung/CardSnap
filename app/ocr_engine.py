import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from PySide6.QtGui import QImage
from typing import List, Optional

from app.card_parser import parse_text

_engine = None
_engine_tuned = None

MIN_SHORT_EDGE = 800
SHARPEN_RADIUS = 1.5
CONTRAST_FACTOR = 1.5


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _get_tuned_engine():
    global _engine_tuned
    if _engine_tuned is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine_tuned = RapidOCR(
            det_db_thresh=0.2,
            det_db_box_thresh=0.4,
        )
    return _engine_tuned


def _preprocess_standard(img: np.ndarray) -> np.ndarray:
    pil = Image.fromarray(img)
    w, h = pil.size
    short_edge = min(w, h)
    if short_edge < MIN_SHORT_EDGE:
        scale = MIN_SHORT_EDGE / short_edge
        pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    pil = ImageEnhance.Contrast(pil).enhance(CONTRAST_FACTOR)
    pil = pil.filter(ImageFilter.UnsharpMask(radius=SHARPEN_RADIUS, percent=150, threshold=3))
    return np.array(pil)


def _preprocess_grayscale(img: np.ndarray) -> np.ndarray:
    pil = Image.fromarray(img)
    w, h = pil.size
    short_edge = min(w, h)
    if short_edge < MIN_SHORT_EDGE:
        scale = MIN_SHORT_EDGE / short_edge
        pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    gray = ImageOps.grayscale(pil)
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=2))
    return np.array(gray.convert("RGB"))


def _preprocess_inverted(img: np.ndarray) -> np.ndarray:
    pil = Image.fromarray(img)
    w, h = pil.size
    short_edge = min(w, h)
    if short_edge < MIN_SHORT_EDGE:
        scale = MIN_SHORT_EDGE / short_edge
        pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    gray = ImageOps.grayscale(pil)
    inverted = ImageOps.invert(gray)
    inverted = ImageEnhance.Contrast(inverted).enhance(2.0)
    return np.array(inverted.convert("RGB"))


def _preprocess_binarize(img: np.ndarray) -> np.ndarray:
    pil = Image.fromarray(img)
    w, h = pil.size
    short_edge = min(w, h)
    if short_edge < MIN_SHORT_EDGE:
        scale = MIN_SHORT_EDGE / short_edge
        pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    gray = ImageOps.grayscale(pil)
    bw = gray.point(lambda x: 255 if x > 128 else 0)
    return np.array(bw.convert("RGB"))


_PREPROCESS_STRATEGIES = [
    ("standard", _preprocess_standard),
    ("grayscale", _preprocess_grayscale),
    ("inverted", _preprocess_inverted),
    ("binarize", _preprocess_binarize),
]


def _run_ocr(img_array: np.ndarray, engine=None) -> List[tuple]:
    if engine is None:
        engine = _get_engine()
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    elif img_array.shape[2] == 4:
        img_array = img_array[:, :, :3]

    result, _ = engine(img_array)
    return result or []


def _result_to_text(result: List[tuple]) -> str:
    if not result:
        return ""
    return "\n".join(item[1] for item in result)


def ocr_from_pil(image: Image.Image) -> str:
    img_array = np.array(image)
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    elif img_array.shape[2] == 4:
        img_array = img_array[:, :, :3]

    processed = _preprocess_standard(img_array)
    result = _run_ocr(processed)
    text = _result_to_text(result)

    if text.strip() and parse_text(text):
        return text

    tuned = _get_tuned_engine()
    for name, preprocess_fn in _PREPROCESS_STRATEGIES:
        try:
            processed = preprocess_fn(img_array)
            result = _run_ocr(processed, tuned)
            candidate = _result_to_text(result)
            if candidate.strip() and parse_text(candidate):
                return candidate
        except Exception:
            continue

    return text


def ocr_from_qimage(qimage: QImage) -> str:
    qimage = qimage.convertToFormat(QImage.Format.Format_RGB888)
    width = qimage.width()
    height = qimage.height()
    bytes_per_line = qimage.bytesPerLine()

    ptr = qimage.bits()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, bytes_per_line))
    arr = arr[:, :width * 3].reshape((height, width, 3))

    image = Image.fromarray(arr)
    return ocr_from_pil(image)
