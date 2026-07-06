import io
import qrcode
from PIL import Image
from PySide6.QtGui import QImage, QPixmap


def generate_qr_image(card_info, box_size: int = 6, border: int = 1) -> Image.Image:
    data = f"{card_info.formatted_number}\n{card_info.expiry}\n{card_info.cvv}"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def qr_to_qpixmap(card_info, size: int = 120) -> QPixmap:
    img = generate_qr_image(card_info, box_size=4, border=2)
    img = img.resize((size, size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    qimg = QImage()
    qimg.loadFromData(buf.read())
    return QPixmap.fromImage(qimg)
